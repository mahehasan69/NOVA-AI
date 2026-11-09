# NOVA AI Cloudflare Worker API

The Worker API uses Cloudflare D1 for durable account and conversation storage. Deploy from this directory with `npx wrangler deploy`. Configure `NOVA_API_KEY` and `JWT_SECRET` as Worker secrets. Add provider secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`, etc.) only if using shared credentials; users can instead supply BYOK keys per request.

The frontend can use the Worker URL as its gateway URL. Register/login endpoints are available; for the current frontend, set the NOVA API key in Settings.


## NOVA Brain

- `PUT /v1/brain/checkpoint` saves a conversation handoff checkpoint (`conversation_id`, `summary`).
- `GET /v1/brain/checkpoint?conversation_id=...` reads the current user's checkpoint.
- `GET /v1/brain/memories` lists the signed-in user's long-term memories.
- `POST /v1/brain/memories` creates a memory (`content`, optional `category`).
- `DELETE /v1/brain/memories/:id` deletes only a memory owned by the signed-in user.

The chat endpoint injects the user's saved memories and conversation checkpoint as context. The frontend saves a recent-transcript handoff checkpoint after successful replies; this is a transcript-based checkpoint, not hidden model reasoning. Users can edit checkpoints and manage long-term memories in the Brain panel.
