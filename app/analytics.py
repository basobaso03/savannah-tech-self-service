from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from threading import Lock
from typing import Any, Iterable
import csv

from app.settings import Settings

ANALYTICS_LOCK = Lock()


@dataclass(frozen=True)
class ChatAnalyticsRecord:
    timestamp: str
    user_id: str | None
    session_id: str | None
    category: str
    question: str
    answer: str
    lead_saved: bool
    matched_chunk_ids: list[int]
    top_score: float | None
    matched_titles: list[str]


@dataclass(frozen=True)
class InsightsSummary:
    total_events: int
    distinct_users: int
    categories: dict[str, int]
    lead_captures: int
    unanswered_requests: int
    average_top_score: float
    top_questions: list[dict[str, Any]]
    top_titles: list[dict[str, Any]]
    top_users: list[dict[str, Any]]
    recommendations: list[str]



def current_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"



def analytics_file(settings: Settings) -> Path:
    return Path(settings.analytics_log_path)



def persist_chat_event(settings: Settings, record: ChatAnalyticsRecord) -> None:
    path = analytics_file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": record.timestamp,
        "user_id": record.user_id,
        "session_id": record.session_id,
        "category": record.category,
        "question": record.question,
        "answer": record.answer,
        "lead_saved": record.lead_saved,
        "matched_chunk_ids": record.matched_chunk_ids,
        "top_score": record.top_score,
        "matched_titles": record.matched_titles,
    }
    with ANALYTICS_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")



def load_chat_events(settings: Settings) -> list[dict[str, Any]]:
    path = analytics_file(settings)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events



def summarize_questions(events: Iterable[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counter = Counter()
    for event in events:
        question = str(event.get("question") or "").strip().lower()
        if question:
            counter[question] += 1
    return [{"question": question, "count": count} for question, count in counter.most_common(limit)]



def summarize_titles(events: Iterable[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counter = Counter()
    for event in events:
        for title in event.get("matched_titles") or []:
            title_text = str(title).strip()
            if title_text:
                counter[title_text] += 1
    return [{"title": title, "count": count} for title, count in counter.most_common(limit)]



def build_insights(settings: Settings) -> InsightsSummary:
    events = load_chat_events(settings)
    categories = Counter(str(event.get("category") or "unknown") for event in events)
    top_scores = [float(event.get("top_score") or 0.0) for event in events if event.get("top_score") is not None]
    average_top_score = sum(top_scores) / len(top_scores) if top_scores else 0.0
    user_counter = Counter(str(event.get("user_id") or "anonymous") for event in events)

    total_events = len(events)
    distinct_users = len(user_counter)
    unanswered_requests = sum(1 for event in events if str(event.get("category") or "") == "company_related_missing")
    lead_captures = sum(1 for event in events if bool(event.get("lead_saved")))

    recommendations: list[str] = []
    if total_events == 0:
        recommendations.append("No chat traffic yet. Start collecting real customer conversations to build insights.")
    if categories.get("greeting", 0) > max(3, total_events // 5):
        recommendations.append("Many users are only greeting the assistant. Add a stronger welcome prompt and a quick-start CTA.")
    if unanswered_requests > max(2, total_events // 4):
        recommendations.append("Company-related missing answers are high. Add more customer docs for pricing, setup, and FAQs.")
    if lead_captures == 0 and total_events > 0:
        recommendations.append("No leads are being captured yet. Improve marketing handoff prompts and onboarding prompts.")
    if average_top_score < 0.45 and total_events > 0:
        recommendations.append("Retrieval confidence is low. Add richer documents or split them into smaller chunks.")
    if not recommendations:
        recommendations.append("The assistant is performing well. Continue monitoring unanswered questions and lead conversion.")

    return InsightsSummary(
        total_events=total_events,
        distinct_users=distinct_users,
        categories=dict(categories),
        lead_captures=lead_captures,
        unanswered_requests=unanswered_requests,
        average_top_score=round(average_top_score, 4),
        top_questions=summarize_questions(events),
        top_titles=summarize_titles(events),
        top_users=[{"user_id": user_id, "count": count} for user_id, count in user_counter.most_common(5)],
        recommendations=recommendations,
    )


def export_events_csv(settings: Settings) -> str:
    events = load_chat_events(settings)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "timestamp",
        "user_id",
        "session_id",
        "category",
        "question",
        "answer",
        "lead_saved",
        "matched_chunk_ids",
        "top_score",
        "matched_titles",
    ])
    for event in events:
        writer.writerow([
            event.get("timestamp", ""),
            event.get("user_id", ""),
            event.get("session_id", ""),
            event.get("category", ""),
            event.get("question", ""),
            event.get("answer", ""),
            bool(event.get("lead_saved")),
            json.dumps(event.get("matched_chunk_ids", []), ensure_ascii=False),
            event.get("top_score", ""),
            json.dumps(event.get("matched_titles", []), ensure_ascii=False),
        ])
    return buffer.getvalue()
