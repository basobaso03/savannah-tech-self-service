from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import requests
from google import genai

from ingest_company_data import build_chunks, embed_text, normalize_embedding_model
from app.settings import Settings


@dataclass(frozen=True)
class KnowledgeChunk:
    id: int
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


@dataclass(frozen=True)
class RankedChunk:
    id: int
    content: str
    metadata: dict[str, Any]
    score: float


class CompanyRetriever:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = normalize_embedding_model(settings.embedding_model)
        self._chunks: list[KnowledgeChunk] = []

    def refresh(self) -> list[KnowledgeChunk]:
        headers = {
            "apikey": self.settings.supabase_api_key,
            "Authorization": f"Bearer {self.settings.supabase_api_key}",
            "Accept": "application/json",
        }
        response = requests.get(
            f"{self.settings.supabase_rest_url}/rest/v1/{self.settings.knowledge_table}",
            headers=headers,
            params={
                "select": "id,content,metadata,embedding",
                "metadata->>source_file": f"eq.{self.settings.source_file}",
                "order": "id.asc",
            },
            timeout=60,
        )
        response.raise_for_status()

        rows = response.json()
        self._chunks = [
            KnowledgeChunk(
                id=int(row["id"]),
                content=str(row["content"]),
                metadata=dict(row.get("metadata") or {}),
                embedding=self._coerce_embedding(row["embedding"]),
            )
            for row in rows
        ]
        return self._chunks

    @staticmethod
    def _coerce_embedding(raw_embedding: Any) -> list[float]:
        if isinstance(raw_embedding, str):
            raw_embedding = json.loads(raw_embedding)
        return [float(value) for value in raw_embedding]

    def _ensure_chunks(self) -> list[KnowledgeChunk]:
        if not self._chunks:
            return self.refresh()
        return self._chunks

    def embed_query(self, question: str) -> list[float]:
        result = embed_text(self.client, question, self.model_name)
        return [float(value) for value in result]

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_magnitude = math.sqrt(sum(a * a for a in left))
        right_magnitude = math.sqrt(sum(b * b for b in right))
        if left_magnitude == 0 or right_magnitude == 0:
            return 0.0
        return numerator / (left_magnitude * right_magnitude)

    def search(self, question: str, top_k: int | None = None) -> list[RankedChunk]:
        query_embedding = self.embed_query(question)
        chunks = self._ensure_chunks()
        ranked = [
            RankedChunk(
                id=chunk.id,
                content=chunk.content,
                metadata=chunk.metadata,
                score=self.cosine_similarity(query_embedding, chunk.embedding),
            )
            for chunk in chunks
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: top_k or self.settings.top_k]
