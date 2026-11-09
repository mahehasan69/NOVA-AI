# NOVA AI Cloudflare Worker API

The Worker API uses Cloudflare D1 for durable account and conversation storage. Deploy from this directory with `npx wrangler deploy`. Configure `NOVA_API_KEY` and `JWT_SECRET` as Worker secrets. Add provider secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`, etc.) only if using shared credentials; users can instead supply BYOK keys per request.

The frontend can use the Worker URL as its gateway URL. Register/login endpoints are available; for the current frontend, set the NOVA API key in Settings.
