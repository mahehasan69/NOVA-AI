# NOVA architecture notes

## Request lifecycle

1. Authenticate the client.
2. Resolve or create a conversation owned by the authenticated user.
3. Load recent messages and the rolling summary.
4. Compile a prompt with the current request and available context.
5. Select only enabled models explicitly marked free.
6. Use a request-scoped BYOK key when supplied; otherwise use the server's shared provider key.
7. Attempt providers in priority order, respecting cooldowns.
8. On quota/rate-limit or transient provider failures, try the next eligible provider.
9. Normalize the successful provider response.
10. Persist user/assistant messages and update the extractive rolling summary.

## Credential rules

- Never commit provider keys.
- Never persist BYOK keys.
- Prefer a KMS-backed secret store for shared credentials in production.
- Never use an API key as proof of user identity.
- Free eligibility is an explicit catalogue flag and must be reviewed by an administrator.

## Failover rules

- 429: cool down provider and try another provider.
- 408, 409, 425, 5xx and network timeout: temporary failure; try another eligible provider.
- 400/401/403: do not retry the same provider; record a sanitized failure and continue only if another credential/provider is configured.
- Never retry indefinitely.
- Never silently switch to a paid model.
- Do not splice a second provider's output into an already-streamed response. Streaming support will use restart semantics in a later release.

## Current limitations

- Cooldown state is process-local. Use a shared durable store for multiple instances.
- The first release uses SQLite and a development identity header. Add production account authentication and PostgreSQL before public multi-tenant launch.
- Provider catalogue entries must be revalidated against current free-tier terms.
- Model-specific multimodal adapters, streaming, rate-limit telemetry, and semantic summarization are planned.
