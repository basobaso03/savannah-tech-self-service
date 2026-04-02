from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterable

from app.schemas import ChatHistoryMessage
from app.settings import Settings

LEAD_LOCK = Lock()
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
CONTACT_REQUEST_PATTERNS = (
    re.compile(r"preferred contact details", re.IGNORECASE),
    re.compile(r"share your contact details", re.IGNORECASE),
    re.compile(r"contact details", re.IGNORECASE),
    re.compile(r"marketing team", re.IGNORECASE),
)


@dataclass(frozen=True)
class LeadCaptureResult:
    saved: bool
    answer: str
    contact_value: str | None = None
    topic: str | None = None


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_contact_value(message: str) -> str | None:
    email_match = EMAIL_PATTERN.search(message)
    if email_match:
        return email_match.group(0)

    phone_match = PHONE_PATTERN.search(message)
    if phone_match:
        return phone_match.group(0).strip()

    return None


def has_pending_contact_request(history: Iterable[ChatHistoryMessage]) -> bool:
    for entry in reversed(list(history)):
        if entry.role != "assistant":
            continue
        if any(pattern.search(entry.content) for pattern in CONTACT_REQUEST_PATTERNS):
            return True
    return False


def last_user_topic(history: Iterable[ChatHistoryMessage]) -> str | None:
    for entry in reversed(list(history)):
        if entry.role == "user" and entry.content.strip():
            return entry.content.strip()
    return None


def persist_lead(settings: Settings, payload: dict) -> None:
    lead_file = settings.lead_capture_file
    lead_file.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_LOCK:
        with lead_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def handle_contact_follow_up(
    settings: Settings,
    session_id: str | None,
    user_message: str,
    history: list[ChatHistoryMessage],
) -> LeadCaptureResult | None:
    contact_value = extract_contact_value(user_message)
    if not contact_value:
        return None

    if not has_pending_contact_request(history):
        return None

    topic = last_user_topic(history)
    record = {
        "timestamp": current_timestamp(),
        "session_id": session_id,
        "contact_value": contact_value,
        "original_request": topic,
        "message": user_message,
    }
    persist_lead(settings, record)

    answer = (
        f"Thanks, I have recorded {contact_value}. Your request has been sent to the marketing team, "
        "and they will contact you soon."
    )
    return LeadCaptureResult(saved=True, answer=answer, contact_value=contact_value, topic=topic)
