# apps/api — Langley demo API + UI

A thin FastAPI layer over the Risk Guardian agent, plus a hand-crafted single-page demo
UI (a "declassified intelligence dossier" theme).

- `GET /` — serves the demo page (`static/index.html`).
- `POST /api/analyze` `{ "query": "<mint-or-symbol>" }` — runs `langley_risk.analyze_token`
  and returns the structured `TokenRiskReport`.
- `GET /docs` — OpenAPI docs.

The router is intentionally thin: it validates input, calls the agent service, and
returns the report. All intelligence lives in `packages/langley_risk`.

## Run

```bash
uv sync
uv run langley-api          # serves on http://127.0.0.1:8000
# or: uv run uvicorn langley_api.main:app --reload --port 8000
```

Needs `OPENAI_API_KEY` in `.env` (and, for contract enrichment, `LANGLEY_RISK_HELIUS_API_KEY`
+ `LANGLEY_RISK_PROVIDER=composite`). The app loads `.env` on startup.
