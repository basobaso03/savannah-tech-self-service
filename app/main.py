from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.analytics import (
    ChatAnalyticsRecord,
    build_insights,
    current_timestamp,
    export_events_csv,
    persist_chat_event,
)
from app.policy import generate_answer
from app.retrieval import CompanyRetriever
from app.schemas import ChatRequest, ChatResponse, InsightsResponse, RetrievedChunk
from app.settings import load_settings

settings = load_settings()
retriever = CompanyRetriever(settings)
app = FastAPI(title="Zimnest Selfservice Chat API", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_knowledge_base() -> None:
    retriever.refresh()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    chunks = retriever.search(question)
    llm_result = generate_answer(
        retriever.client,
        settings,
        question,
        chunks,
        history=payload.history,
        session_id=payload.session_id,
    )
    matched_chunks = [
        RetrievedChunk(
            id=chunk.id,
            score=round(chunk.score, 4),
            content=chunk.content,
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]
    persist_chat_event(
        settings,
        ChatAnalyticsRecord(
            timestamp=current_timestamp(),
            user_id=payload.user_id,
            session_id=payload.session_id,
            category=str(llm_result["category"]),
            question=question,
            answer=str(llm_result["answer"]),
            lead_saved=bool(llm_result.get("lead_saved", False)),
            matched_chunk_ids=[chunk.id for chunk in chunks],
            top_score=chunks[0].score if chunks else None,
            matched_titles=[str(chunk.metadata.get("title") or "") for chunk in chunks if chunk.metadata.get("title")],
        ),
    )
    return ChatResponse(
        category=llm_result["category"],
        answer=llm_result["answer"],
        matched_chunks=matched_chunks,
        lead_saved=bool(llm_result.get("lead_saved", False)),
        suggestions=list(llm_result.get("suggestions", [])),
    )


@app.post("/chat/insights", response_model=InsightsResponse)
def chat_insights() -> InsightsResponse:
    summary = build_insights(settings)
    return InsightsResponse(
        total_events=summary.total_events,
        distinct_users=summary.distinct_users,
        categories=summary.categories,
        lead_captures=summary.lead_captures,
        unanswered_requests=summary.unanswered_requests,
        average_top_score=summary.average_top_score,
        top_questions=summary.top_questions,
        top_titles=summary.top_titles,
        top_users=summary.top_users,
        recommendations=summary.recommendations,
    )


@app.get("/chat/insights/export")
def export_chat_insights() -> Response:
    csv_text = export_events_csv(settings)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="chat_analytics.csv"'},
    )
