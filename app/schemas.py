from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    name: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")


class ChatRequest(BaseModel):
    user_id: str | None = Field(default=None, alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    message: str = Field(min_length=1, description="User question or message")
    history: list[ChatHistoryMessage] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    id: int
    score: float
    content: str
    metadata: dict[str, Any]


class ChatResponse(BaseModel):
    category: str
    answer: str
    matched_chunks: list[RetrievedChunk]
    lead_saved: bool = False
    suggestions: list[str] = Field(default_factory=list)


class InsightsResponse(BaseModel):
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
