# Deployment Notes

This project now includes a lead-capture path for company-related requests that need human follow-up.

Deployment-impacting items:
- The backend writes marketing lead handoffs to `data/marketing_leads.jsonl` by default.
- In production, that path needs persistent storage or it should be replaced with a real lead destination such as email, CRM, or a database table.
- The frontend still needs `VITE_API_BASE_URL` set to the deployed FastAPI URL before building.
- FastAPI CORS must allow the deployed frontend origin.
- The frontend stores chat sessions in browser local storage, so that history is client-side only.

No schema changes are required for the existing Supabase company knowledge table.
