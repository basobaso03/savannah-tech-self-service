# Deployment Impact Notes

This change adds a React frontend that talks to the FastAPI backend, so deployment now has two moving parts:

1. The frontend must be built with Vite and served as static assets.
2. The FastAPI backend must allow the frontend origin through CORS.
3. The frontend needs `VITE_API_BASE_URL` pointing at the deployed FastAPI service.
4. The backend should keep the existing `/chat` contract stable so the UI can continue to work without changes.

If you deploy both services under the same domain or reverse proxy, the CORS impact is smaller. If you deploy them separately, update the frontend API base URL and the backend allowed origins before release.
