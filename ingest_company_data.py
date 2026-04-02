"""Ingest company data into Supabase using Gemini embeddings.

Reads company_data.txt, splits it into semantic chunks, generates Gemini
embeddings, and stores the content, metadata, and vector in the
zimnest_company_data table.

Environment variables are loaded from .env.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from typing import Iterable, List

from dotenv import load_dotenv
from google import genai
import psycopg
from psycopg import sql
from psycopg.types.json import Json
import requests


@dataclass
class Chunk:
    content: str
    metadata: dict


def env_value(*names: str, required: bool = False, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    if required:
        raise ValueError(f"Missing required environment variable. Tried: {', '.join(names)}")
    return default


def normalize_embedding_model(model_name: str) -> str:
    model_name = model_name.strip()
    legacy_models = {"text-embedding-004", "models/gemini-embedding-004"}
    if model_name in legacy_models:
        return "gemini-embedding-001"
    if model_name.startswith("models/") or model_name.startswith("gemini-"):
        return model_name
    return f"models/{model_name}"


def read_text_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def build_supabase_rest_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or ""
    if host.startswith("db."):
        host = host[3:]
    return f"https://{host}"


def split_into_chunks(text: str, max_chars: int = 1200) -> List[str]:
    """Split text into semantic chunks while preserving headings and paragraphs."""

    text = text.replace("\r\n", "\n").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current).strip())
            current = []
            current_len = 0

    for paragraph in paragraphs:
        # Start a new chunk on markdown headings when we already have content.
        if re.match(r"^#{1,6}\s+", paragraph) and current:
            flush()

        if len(paragraph) > max_chars:
            flush()
            # Split long paragraphs on sentence boundaries, then by size if needed.
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            buffer = ""
            for sentence in sentences:
                if not sentence:
                    continue
                if len(sentence) > max_chars:
                    # Hard wrap extremely long sentences.
                    start = 0
                    while start < len(sentence):
                        chunks.append(sentence[start : start + max_chars].strip())
                        start += max_chars
                    buffer = ""
                    continue
                candidate = f"{buffer} {sentence}".strip() if buffer else sentence
                if len(candidate) <= max_chars:
                    buffer = candidate
                else:
                    if buffer:
                        chunks.append(buffer.strip())
                    buffer = sentence
            if buffer:
                chunks.append(buffer.strip())
            continue

        candidate_len = current_len + len(paragraph) + (2 if current else 0)
        if current and candidate_len > max_chars:
            flush()

        current.append(paragraph)
        current_len += len(paragraph) + (2 if len(current) > 1 else 0)

    flush()
    return [chunk for chunk in chunks if chunk.strip()]


def build_chunks(text: str, source_name: str, max_chars: int) -> List[Chunk]:
    raw_chunks = split_into_chunks(text, max_chars=max_chars)
    chunks: List[Chunk] = []

    for index, content in enumerate(raw_chunks, start=1):
        heading_match = re.search(r"^#{1,6}\s+(.+)$", content, flags=re.MULTILINE)
        title = heading_match.group(1).strip() if heading_match else None
        metadata = {
            "source_file": source_name,
            "chunk_index": index,
            "char_count": len(content),
            "title": title,
        }
        chunks.append(Chunk(content=content, metadata=metadata))

    return chunks


def embed_text(client: genai.Client, text: str, model_name: str) -> list[float]:
    result = client.models.embed_content(
        model=model_name,
        contents=text,
        config={"output_dimensionality": 768},
    )
    embeddings = getattr(result, "embeddings", None)
    if not embeddings:
        raise RuntimeError("Gemini embedding response did not contain embeddings.")

    values = getattr(embeddings[0], "values", None)
    if values is None:
        raise RuntimeError("Gemini embedding response did not contain embedding values.")
    return list(values)


def insert_chunks(
    connection: psycopg.Connection,
    table_name: str,
    chunks: Iterable[Chunk],
    embedding_model: str,
    client: genai.Client,
) -> int:
    inserted = 0
    insert_query = sql.SQL("INSERT INTO {} (content, metadata, embedding) VALUES (%s, %s, %s)").format(
        sql.Identifier(table_name)
    )
    with connection.cursor() as cursor:
        for chunk in chunks:
            embedding = embed_text(client, chunk.content, embedding_model)
            if len(embedding) != 768:
                raise ValueError(
                    f"Expected 768-dimensional embedding, got {len(embedding)} dimensions. "
                    "Check the embedding model and table schema."
                )

            cursor.execute(insert_query, (chunk.content, Json(chunk.metadata), embedding))
            inserted += 1
    connection.commit()
    return inserted


def delete_existing_chunks(
    connection: psycopg.Connection,
    table_name: str,
    source_file: str,
) -> int:
    delete_query = sql.SQL("DELETE FROM {} WHERE metadata->>'source_file' = %s").format(sql.Identifier(table_name))
    with connection.cursor() as cursor:
        cursor.execute(delete_query, (source_file,))
        deleted = cursor.rowcount or 0
    connection.commit()
    return deleted


def insert_chunks_via_rest(
    rest_url: str,
    api_key: str,
    table_name: str,
    chunks: Iterable[Chunk],
    embedding_model: str,
    client: genai.Client,
) -> int:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    inserted = 0
    endpoint = f"{rest_url}/rest/v1/{table_name}"

    for chunk in chunks:
        embedding = embed_text(client, chunk.content, embedding_model)
        if len(embedding) != 768:
            raise ValueError(
                f"Expected 768-dimensional embedding, got {len(embedding)} dimensions. "
                "Check the embedding model and table schema."
            )

        payload = {
            "content": chunk.content,
            "metadata": chunk.metadata,
            "embedding": embedding,
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"Supabase REST insert failed for chunk {chunk.metadata.get('chunk_index')}: "
                f"{response.status_code} {response.text}"
            )
        inserted += 1

    return inserted


def delete_existing_chunks_via_rest(rest_url: str, api_key: str, table_name: str, source_file: str) -> int:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Prefer": "return=minimal",
    }
    endpoint = f"{rest_url}/rest/v1/{table_name}"
    response = requests.delete(
        endpoint,
        headers=headers,
        params={"metadata->>source_file": f"eq.{source_file}"},
        timeout=60,
    )
    if response.status_code not in (200, 202, 204):
        raise RuntimeError(f"Supabase REST delete failed: {response.status_code} {response.text}")
    return 0


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chunk company data, embed it with Gemini, and store it in Supabase.")
    parser.add_argument(
        "--input",
        default="company_data.txt",
        help="Path to the company data text file.",
    )
    parser.add_argument(
        "--table",
        default="zimnest_company_data",
        help="Destination table name.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Maximum characters per chunk.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunks without writing to the database.",
    )
    args = parser.parse_args()

    gemini_api_key = env_value("gemini_api_key", "GEMINI_API_KEY", required=True)
    embedding_model = env_value("embedding_model", "EMBEDDING_MODEL", default="gemini-embedding-001")
    database_url = env_value(
        "superbase_Url",
        "SUPABASE_DB_URL",
        "SUPABASE_URL",
        required=True,
    )
    supabase_api_key = env_value("superbase_Api_Key", "SUPABASE_API_KEY", required=True)

    normalized_model = normalize_embedding_model(embedding_model)
    client = genai.Client(api_key=gemini_api_key)
    rest_url = build_supabase_rest_url(database_url)

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path

    text = read_text_file(input_path)
    chunks = build_chunks(text, input_path.name, max_chars=args.max_chars)

    if not chunks:
        raise RuntimeError(f"No chunks were produced from {input_path.name}.")

    print(f"Prepared {len(chunks)} chunks from {input_path.name}.")
    for chunk in chunks:
        print(json.dumps(chunk.metadata, ensure_ascii=False))

    if args.dry_run:
        return

    try:
        with psycopg.connect(database_url) as connection:
            from pgvector.psycopg import register_vector

            register_vector(connection)
            deleted = delete_existing_chunks(connection, args.table, input_path.name)
            if deleted:
                print(f"Deleted {deleted} existing rows for {input_path.name} via Postgres.")
            inserted = insert_chunks(connection, args.table, chunks, normalized_model, client)
        print(f"Inserted {inserted} chunks into {args.table} via Postgres.")
        return
    except psycopg.OperationalError as exc:
        print(f"Postgres connection failed, falling back to Supabase REST: {exc}")

    delete_existing_chunks_via_rest(rest_url, supabase_api_key, args.table, input_path.name)
    inserted = insert_chunks_via_rest(rest_url, supabase_api_key, args.table, chunks, normalized_model, client)

    print(f"Inserted {inserted} chunks into {args.table} via Supabase REST.")


if __name__ == "__main__":
    main()
