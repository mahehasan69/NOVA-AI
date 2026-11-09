# NOVA Web App (Phase 3)

A zero-build, mobile-responsive frontend for the NOVA FastAPI gateway.

## Run locally

1. Start the backend from the repository root: `uvicorn app.main:app --reload`.
2. From the repository root run `python -m http.server 3000 --directory frontend`.
3. Visit `http://localhost:3000`. The default gateway URL is `http://localhost:8000`.
4. In Settings, configure the gateway URL and, if configured on the backend, its `NOVA_API_KEY`. Optionally provide BYOK provider keys.

The backend allows the localhost:3000 origin by default. For a different frontend origin, configure backend CORS before use.

## Security and limitations

- **Development/trusted use only**: the backend does not yet have real user login. Do not expose this frontend and gateway as a public multi-user product.
- Gateway URL and chat previews are saved in **sessionStorage**, not long-term storage. Gateway and provider API keys remain in JavaScript memory only, and clear on reload.
- BYOK keys are sent to the configured gateway, so only use your own trusted gateway over HTTPS (or localhost HTTP).
- The interface renders AI replies as plain text, not executable HTML or Markdown.
- This is a non-streaming text chat UI. Refreshing loses API keys; the server retains conversation history, but the frontend only tracks session-local conversation IDs.
- No paid UI libraries, build tooling, or frontend hosting requirements.
