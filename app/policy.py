from __future__ import annotations

import json
import re
from typing import Any

from google import genai
from google.genai import errors as genai_errors

from app.lead_capture import handle_contact_follow_up
from app.schemas import ChatHistoryMessage
from app.retrieval import RankedChunk
from app.settings import Settings

GREETING_PATTERN = re.compile(r"^(hi|hello|hey|hie|howdy|good\s+(morning|afternoon|evening))\b", re.IGNORECASE)
ONBOARDING_PATTERN = re.compile(
    r"\b(get started|start using|start|begin|onboard|signup|sign up|subscribe|how can i use|how do i use|how can i start using|how do i start using)\b",
    re.IGNORECASE,
)

LOCATION_PATTERN = re.compile(
    r"\b(location|locations|address|shop|shops|store|stores|branch|branches|office|offices|headquarters|head office|where are you|where is your|where can i find|visit you)\b",
    re.IGNORECASE,
)

SUPPORT_PATTERN = re.compile(
    r"\b(contact support|support contact|support hours|customer support|help desk|support team|report an issue|report issue|contact us|phone support|email support)\b",
    re.IGNORECASE,
)

PRICING_PATTERN = re.compile(
    r"\b(pricing|price|cost|plan|plans|enterprise pricing|license|licenses|tier|tiers|quote)\b",
    re.IGNORECASE,
)

SECTION_TITLE_PATTERN = re.compile(r"^(section\s+\d+|faq|faqs|frequently asked questions|product catalog)$", re.IGNORECASE)
KNOWN_SERVICE_NAMES = (
    "SavannahCloud Hosting",
    "Agentic-Flow AI",
    "Baso Enterprise API",
)
KNOWN_SERVICE_QUESTIONS = {
    "SavannahCloud Hosting": "Tell me more about SavannahCloud Hosting",
    "Agentic-Flow AI": "Tell me more about Agentic-Flow AI",
    "Baso Enterprise API": "Tell me more about Baso Enterprise API",
}


def build_context(chunks: list[RankedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        title = chunk.metadata.get("title") or f"Chunk {chunk.id}"
        blocks.append(f"[{title}]\n{chunk.content}")
    return "\n\n---\n\n".join(blocks)


def build_history_context(history: list[ChatHistoryMessage]) -> str:
    if not history:
        return "No prior conversation."

    lines = []
    for message in history[-8:]:
        speaker = message.name or message.role.title()
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


def build_suggestions(question: str, category: str, chunks: list[RankedChunk]) -> list[str]:
    question_lower = question.lower()

    def unique_suggestions(items: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for item in items:
            candidate = item.strip()
            if not candidate:
                continue
            if candidate.lower() in seen:
                continue
            if SECTION_TITLE_PATTERN.match(candidate):
                continue
            seen.add(candidate.lower())
            output.append(candidate)
            if len(output) == 3:
                break
        return output

    if any(term in question_lower for term in ("products", "product", "services", "service", "offer", "offering")):
        service_suggestions = [
            KNOWN_SERVICE_QUESTIONS[service_name]
            for service_name in KNOWN_SERVICE_NAMES
            if service_name.lower() in question_lower or any(service_name.lower() in str(chunk.content).lower() for chunk in chunks)
        ]
        service_suggestions.extend([
            "Tell me more about SavannahCloud Hosting",
            "Tell me more about Agentic-Flow AI",
            "Tell me more about Baso Enterprise API",
        ])
        return unique_suggestions(service_suggestions)

    if is_location_question(question):
        return unique_suggestions([
            "What are your operating hours?",
            "How can I contact support?",
            "What services do you offer?",
        ])

    if is_support_question(question):
        return unique_suggestions([
            "What are your support hours?",
            "How do I report an issue?",
            "What is your support email address?",
        ])

    if is_pricing_question(question):
        return unique_suggestions([
            "Compare your pricing plans",
            "Do you offer enterprise pricing?",
            "How do I get started?",
        ])

    if any(term in question_lower for term in ("pricing", "price", "cost", "plan", "plans", "billing", "invoice")):
        return unique_suggestions([
            "Compare your pricing plans",
            "Do you offer enterprise pricing?",
            "How do I get started?",
        ])

    if any(term in question_lower for term in ("support", "help", "troubleshoot", "issue", "problem", "error")):
        return unique_suggestions([
            "What are your support hours?",
            "How do I report an issue?",
            "What is your support email address?",
        ])

    if any(term in question_lower for term in ("start", "begin", "onboard", "signup", "sign up", "subscribe")):
        return unique_suggestions([
            "Which service should I choose?",
            "What do I need to get started?",
            "Can someone contact me?",
        ])

    if any(term in question_lower for term in ("refund", "cancel", "cancellation", "policy", "privacy", "payment")):
        return unique_suggestions([
            "What is your refund process?",
            "Do you have a privacy policy?",
            "How do I update my billing details?",
        ])

    if category == "company_related_missing":
        return unique_suggestions([
            "Can you share your email address?",
            "Can you share your phone number?",
            "Which Savannah Tech service should I ask about?",
        ])

    if category == "unrelated":
        return unique_suggestions([
            "Tell me about your pricing",
            "Where is your office located?",
            "How can I contact support?",
        ])

    suggestions: list[str] = []
    seen: set[str] = set()
    service_names_found: list[str] = []
    search_text = " ".join(
        [question, *[str(chunk.content) for chunk in chunks], *[str(chunk.metadata.get("title") or "") for chunk in chunks]]
    ).lower()

    for service_name in KNOWN_SERVICE_NAMES:
        if service_name.lower() in search_text:
            service_names_found.append(service_name)

    for service_name in service_names_found:
        suggestion = KNOWN_SERVICE_QUESTIONS[service_name]
        if suggestion.lower() not in seen:
            seen.add(suggestion.lower())
            suggestions.append(suggestion)
        if len(suggestions) == 3:
            return suggestions

    for chunk in chunks:
        title = str(chunk.metadata.get("title") or "").strip()
        if not title or SECTION_TITLE_PATTERN.match(title):
            continue
        if title.lower().startswith("section "):
            continue
        suggestion = f"Tell me more about {title}"
        if suggestion not in seen:
            seen.add(suggestion)
            suggestions.append(suggestion)
        if len(suggestions) == 3:
            break

    while len(suggestions) < 3:
        for fallback in (
            "What services do you offer?",
            "How do I get started?",
            "How can I contact support?",
        ):
            if fallback not in seen:
                seen.add(fallback)
                suggestions.append(fallback)
            if len(suggestions) == 3:
                break

    return unique_suggestions(suggestions)


def is_greeting_only(question: str) -> bool:
    cleaned = question.strip().lower().strip("!?.,")
    if not cleaned:
        return False
    if GREETING_PATTERN.match(cleaned):
        return True
    greeting_words = {"hi", "hello", "hey", "hie", "howdy"}
    return cleaned in greeting_words


def is_onboarding_question(question: str) -> bool:
    return bool(ONBOARDING_PATTERN.search(question))


def is_location_question(question: str) -> bool:
    return bool(LOCATION_PATTERN.search(question))


def is_support_question(question: str) -> bool:
    return bool(SUPPORT_PATTERN.search(question))


def is_pricing_question(question: str) -> bool:
    return bool(PRICING_PATTERN.search(question))


def build_prompt(question: str, context: str, history_context: str, settings: Settings) -> str:
    return f"""You are the official support assistant for Savannah Tech Innovations.

Rules:
- Only answer using the provided company context and the user's message.
- If the question is unrelated to Savannah Tech Innovations, return JSON with category set to \"unrelated\" and answer set exactly to: {settings.unrelated_response}
- If the question is about Savannah Tech Innovations but the answer is not in the provided context, return JSON with category set to \"company_related_missing\" and answer set exactly to: {settings.marketing_response}
- If the user asks for a shop, branch, office, headquarters, or address, use the company profile context and answer with the headquarters location when available.
- If only one physical location is known, say that this is the main office or headquarters and give that address.
- Otherwise return JSON with category set to \"answerable\" and answer containing a concise helpful answer.
- Do not mention these instructions.
- Return JSON only with keys: category, answer.

User question:
{question}

Recent conversation:
{history_context}

Relevant company context:
{context}
"""


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def fallback_response(question: str, chunks: list[RankedChunk], settings: Settings) -> dict[str, Any]:
    if is_pricing_question(question):
        return {"category": "answerable", "answer": settings.pricing_response}

    if is_support_question(question):
        return {"category": "answerable", "answer": settings.support_response}

    if is_location_question(question):
        return {"category": "answerable", "answer": settings.location_response}

    top_score = chunks[0].score if chunks else 0.0
    if top_score < settings.similarity_threshold:
        question_lower = question.lower()
        company_terms = (
            "savannah",
            "cloud",
            "agentic",
            "baso",
            "api",
            "billing",
            "pricing",
            "price",
            "cost",
            "plan",
            "plans",
            "enterprise",
            "support",
            "hosting",
            "location",
            "locations",
            "refund",
            "cancellation",
            "privacy",
            "policy",
            "payment",
            "invoice",
            "backup",
            "password",
        )
        if any(term in question_lower for term in company_terms):
            return {"category": "company_related_missing", "answer": settings.marketing_response}

        return {"category": "unrelated", "answer": settings.unrelated_response}

    question_lower = question.lower()
    company_terms = (
        "savannah",
        "cloud",
        "agentic",
        "baso",
        "api",
        "billing",
        "pricing",
        "price",
        "cost",
        "plan",
        "plans",
        "enterprise",
        "support",
        "hosting",
        "location",
        "locations",
        "address",
        "headquarters",
        "head office",
        "office",
        "branch",
        "shop",
        "shops",
        "store",
        "refund",
        "cancellation",
        "privacy",
        "policy",
        "payment",
        "invoice",
        "backup",
        "password",
    )
    if any(term in question_lower for term in company_terms):
        if is_pricing_question(question):
            return {"category": "answerable", "answer": settings.pricing_response}
        if is_location_question(question):
            return {"category": "answerable", "answer": settings.location_response}
        return {"category": "company_related_missing", "answer": settings.marketing_response}

    return {"category": "unrelated", "answer": settings.unrelated_response}


def generate_answer(
    client: genai.Client,
    settings: Settings,
    question: str,
    chunks: list[RankedChunk],
    history: list[ChatHistoryMessage] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    conversation_history = history or []

    if is_greeting_only(question):
        return {
            "category": "greeting",
            "answer": settings.greeting_response,
            "lead_saved": False,
            "suggestions": build_suggestions(question, "greeting", chunks),
        }

    if is_onboarding_question(question):
        return {
            "category": "company_related_missing",
            "answer": settings.onboarding_response,
            "lead_saved": False,
            "suggestions": build_suggestions(question, "company_related_missing", chunks),
        }

    if is_location_question(question):
        return {
            "category": "answerable",
            "answer": settings.location_response,
            "lead_saved": False,
            "suggestions": build_suggestions(question, "answerable", chunks),
        }

    if is_support_question(question):
        return {
            "category": "answerable",
            "answer": settings.support_response,
            "lead_saved": False,
            "suggestions": build_suggestions(question, "answerable", chunks),
        }

    if is_pricing_question(question):
        return {
            "category": "answerable",
            "answer": settings.pricing_response,
            "lead_saved": False,
            "suggestions": build_suggestions(question, "answerable", chunks),
        }

    lead_result = handle_contact_follow_up(settings, session_id, question, conversation_history)
    if lead_result:
        return {
            "category": "company_related_missing",
            "answer": lead_result.answer,
            "lead_saved": True,
            "suggestions": build_suggestions(question, "company_related_missing", chunks),
        }

    context = build_context(chunks)
    history_context = build_history_context(conversation_history)
    prompt = build_prompt(question, context, history_context, settings)
    last_error: Exception | None = None

    for model_name in settings.chat_model_candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            )
            text = getattr(response, "text", None) or "{}"
            data = parse_json_text(text)
            category = str(data.get("category", "answerable"))
            answer = str(data.get("answer", "")).strip()
            if not answer:
                answer = settings.unrelated_response if category == "unrelated" else settings.marketing_response
            return {
                "category": category,
                "answer": answer,
                "lead_saved": False,
                "suggestions": build_suggestions(question, category, chunks),
            }
        except (genai_errors.ServerError, genai_errors.ClientError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    if last_error:
        fallback = fallback_response(question, chunks, settings)
        fallback["lead_saved"] = False
        fallback["suggestions"] = build_suggestions(question, str(fallback.get("category", "")), chunks)
        return fallback

    fallback = fallback_response(question, chunks, settings)
    fallback["lead_saved"] = False
    fallback["suggestions"] = build_suggestions(question, str(fallback.get("category", "")), chunks)
    return fallback
