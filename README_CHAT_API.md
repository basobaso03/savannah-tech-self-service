# Zimnest Selfservice Chat API

## Run

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Chat endpoint

`POST /chat`

Example body:

```json
{
  "message": "What payment methods do you accept?"
}
```

The API retrieves the most relevant chunks from the Supabase table, ranks them with vector similarity, sends the chunks plus the user question to Gemini, and returns the answer.
