from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from ingest_company_data import build_supabase_rest_url, env_value, normalize_embedding_model


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    supabase_api_key: str
    supabase_db_url: str
    supabase_rest_url: str
    embedding_model: str
    chat_model: str
    fallback_chat_model: str
    secondary_fallback_chat_model: str
    lead_capture_path: str
    analytics_log_path: str
    knowledge_table: str = "zimnest_company_data"
    source_file: str = "company_data.txt"
    top_k: int = 4
    similarity_threshold: float = 0.18

    @property
    def chat_model_candidates(self) -> list[str]:
        return [
            self.chat_model,
            self.fallback_chat_model,
            self.secondary_fallback_chat_model,
        ]

    @property
    def lead_capture_file(self):
        from pathlib import Path

        return Path(self.lead_capture_path)

    @property
    def analytics_file(self):
        from pathlib import Path

        return Path(self.analytics_log_path)

    @property
    def marketing_response(self) -> str:
        return (
            "I don't have that information right now. Please share your preferred contact "
            "details (email or phone number), and I will send your request to the marketing "
            "team so they can contact you soon."
        )

    @property
    def unrelated_response(self) -> str:
        return "I can only help with questions about Savannah Tech Innovations and its services."

    @property
    def greeting_response(self) -> str:
        return (
            "Hello. I'm Savannah Tech Assistant. Ask me about Savannah Tech Innovations, "
            "and I'll help with products, support, pricing, policies, or troubleshooting."
        )

    @property
    def location_response(self) -> str:
        return (
            "Savannah Tech Innovations has one main physical location: 145 Enterprise Road, "
            "Highlands, Harare, Zimbabwe. This is the main headquarters and customer-facing office."
        )

    @property
    def support_response(self) -> str:
        return (
            "You can contact support at support@savannahtech.co.zw or call +263 242 700 111. "
            "Support is available Monday to Friday, 08:00 CAT to 17:00 CAT."
        )

    @property
    def pricing_response(self) -> str:
        return (
            "Savannah Tech Innovations pricing includes: SavannahCloud Hosting (Basic $15/month, "
            "Pro $45/month, Enterprise from $150/month custom), Agentic-Flow AI (Developer $30/month per seat, "
            "Business $99/month per seat), and Baso Enterprise API (Starter free up to 10,000 messages/month, "
            "Growth $50/month, Scale $200/month)."
        )

    @property
    def onboarding_response(self) -> str:
        return (
            "To get started, choose a service you want to explore: SavannahCloud Hosting, "
            "Agentic-Flow AI, or Baso Enterprise API. If you want help choosing the right option, "
            "please share your preferred contact details (email or phone number), and I'll send "
            "your request to the marketing team so they can contact you soon."
        )



def load_settings() -> Settings:
    load_dotenv()

    gemini_api_key = env_value("gemini_api_key", "GEMINI_API_KEY", required=True)
    supabase_api_key = env_value("superbase_Api_Key", "SUPABASE_API_KEY", required=True)
    supabase_db_url = env_value("superbase_Url", "SUPABASE_DB_URL", "SUPABASE_URL", required=True)
    embedding_model = normalize_embedding_model(
        env_value("embedding_model", "EMBEDDING_MODEL", default="gemini-embedding-001")
    )
    chat_model = env_value("gemini_chat_model", "GEMINI_CHAT_MODEL", default="gemini-2.5-flash")
    fallback_chat_model = env_value("gemini_fallback_model", "GEMINI_FALLBACK_MODEL", default="gemini-2.5-flash-lite")
    secondary_fallback_chat_model = env_value(
        "gemini_fallback_model-2",
        "gemini_fallback_model_2",
        "GEMINI_FALLBACK_MODEL_2",
        default="gemini-2.5-pro",
    )
    lead_capture_path = env_value(
        "lead_capture_path",
        "LEAD_CAPTURE_PATH",
        default="data/marketing_leads.jsonl",
    )
    analytics_log_path = env_value(
        "analytics_log_path",
        "ANALYTICS_LOG_PATH",
        default="data/chat_analytics.jsonl",
    )

    return Settings(
        gemini_api_key=gemini_api_key,
        supabase_api_key=supabase_api_key,
        supabase_db_url=supabase_db_url,
        supabase_rest_url=build_supabase_rest_url(supabase_db_url),
        embedding_model=embedding_model,
        chat_model=chat_model,
        fallback_chat_model=fallback_chat_model,
        secondary_fallback_chat_model=secondary_fallback_chat_model,
        lead_capture_path=lead_capture_path,
        analytics_log_path=analytics_log_path,
    )
