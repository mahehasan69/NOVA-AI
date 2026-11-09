# NOVA AI

**Universal Free-First AI Gateway & Conversation Continuity Engine**

NOVA routes chat requests across multiple AI providers, prioritizes explicitly configured free models, preserves conversation history, and retries eligible providers when rate limits or temporary outages occur.

> Free-first does not mean unlimited. Provider quotas, model availability, eligibility, and terms change. NOVA never bypasses provider limits.

## Core capabilities

- Provider adapter architecture (OpenAI-compatible APIs and Google Gemini)
- Free-model allowlist: only models explicitly marked `free: true` are routable
- Automatic failover on rate limits, temporary server errors, and timeouts
- Persistent, user-isolated conversation history in SQLite
- Context-window-aware prompt construction and rolling conversation summaries
- Shared server credentials and per-request BYOK credentials
- OpenAI-compatible `POST /v1/chat/completions` endpoint
- Provider health and model discovery endpoints
- No API keys stored in conversation history or returned in responses

## Quick start

1. Copy `.env.example` to `.env` and configure at least one provider key.
2. Install Python 3.11+ and dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
3. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Open `http://localhost:8000/docs`.

## Configuration

Provider credentials are read from environment variables. For BYOK, send the key in the `provider_keys` object in the JSON request body over HTTPS. BYOK keys are request-scoped, never written to the database, and are not returned in responses.

Set `NOVA_API_KEY` before exposing the API publicly. In development only, an empty value permits local requests. The current `X-NOVA-User` identity header is a development/trusted-gateway mechanism, not end-user authentication. Do not expose this API directly to untrusted users until a real account/JWT authentication layer is implemented.

The default model catalogue is in `config/models.json`. A model is eligible only when `free` is true and `enabled` is true. Verify provider pricing and free-tier eligibility before enabling a model. Set `free: false` to exclude a model.

## Chat request

Send only the new turn when using a conversation ID; NOVA loads prior turns from its database. A full OpenAI-style message history is also accepted and NOVA attempts to detect the overlap with stored history.

```json
{
  "model": "auto",
  "messages": [
    {"role": "user", "content": "Explain how photosynthesis works."}
  ],
  "conversation_id": "optional-existing-id",
  "provider_keys": {
    "groq": "YOUR_OWN_GROQ_KEY"
  }
}
```

Use `model: "auto"` for automatic selection or a registered model ID to request a specific model. A specific model request may still fail over to another eligible free model unless `allow_fallback` is false.

## API endpoints

- `GET /health` — service health
- `GET /v1/models` — enabled free models
- `GET /v1/providers` — provider readiness (never exposes credentials)
- `POST /v1/chat/completions` — OpenAI-compatible chat endpoint
- `GET /v1/conversations/{conversation_id}` — authenticated user's conversation history

## Architecture

```
Client -> API/Auth -> Conversation Store -> Prompt Engine
      -> Free Model Router -> Provider Adapter -> AI Provider
      <- Normalized response <- Failover / quota handling
```

## Important production notes

- Use HTTPS for all BYOK requests.
- Use a managed secrets vault/KMS for shared credentials in production.
- Replace the in-memory cooldown tracker with Redis or a durable shared store for multi-instance deployments.
- Configure per-user request, token, and concurrency limits before public launch.
- Add real account authentication/JWT and PostgreSQL before public multi-user deployment.
- SQLite is suitable for local development and a small single-instance deployment.
- Provider APIs and free tiers can change. Check current provider documentation and terms.

## License

MIT
