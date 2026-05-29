# apps/api — FastAPI Backend (placeholder)

> 🅿️ **Not implemented yet.** This is a reserved home in the monorepo.

The HTTP API that will expose the agents to the frontend and external clients.

**Planned stack:** FastAPI · Supabase (DB + Auth) · deployed on a Python host.

When built, it will be a **thin** layer over the agent packages: it imports `langley_risk` (and later the other agents), exposes endpoints that validate input, call the package's service entrypoint (e.g. `analyze_token`), and return the structured report. No business logic lives here — routers stay thin, the intelligence lives in the agent packages.

See [`docs/architecture.md`](../../docs/architecture.md) for the roadmap.
