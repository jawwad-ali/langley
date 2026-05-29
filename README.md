# Langley

> Your Private Crypto Intelligence Agency — a multi-agent AI system that monitors on-chain data, social chatter, and market psychology, then collaborates and cross-verifies before handing you ranked, evidence-cited insights.

This repository is a **monorepo**. We are building it one agent at a time, starting with the highest-stakes, most-provable agent — the **Risk Guardian** — before adding breadth. See [`docs/architecture.md`](docs/architecture.md) for the full vision and the "risk-first" rationale.

## Status

| Component | State |
|-----------|-------|
| `packages/langley_risk` — **Risk Guardian** | ✅ Implemented (vertical slice + eval harness) |
| Other 6 agents | 🅿️ Placeholder homes only |
| `apps/api` (FastAPI) · `apps/web` (Next.js) | 🅿️ Placeholder homes only |

## Repository layout

```
packages/        Python agent packages (only langley_risk is built)
apps/            Deployable apps — api (FastAPI), web (Next.js)   [placeholders]
docs/            Architecture + roadmap
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) ≥ 0.9 (manages Python 3.12 + dependencies)
- An `OPENAI_API_KEY` (only needed to run the *live* agent / live evals)

## Quickstart

```bash
# 1. Install the workspace (provisions Python 3.12 + all deps into .venv)
uv sync

# 2. Copy env template and add your OpenAI key (only needed for live runs)
cp .env.example .env

# 3. Quality gates (no network, no OpenAI spend)
uv run ruff check .       # lint
uv run pyright            # strict type check
uv run pytest -m "not live"   # unit + offline eval tests

# 4. Offline eval harness — precision/recall/F1 over the golden dataset
uv run python -m langley_risk.evals.run

# 5. Live analysis of a real token (needs OPENAI_API_KEY)
uv run python -m langley_risk "So11111111111111111111111111111111111111112"
```

On Linux/macOS (or Windows with `make`), the same commands are wrapped in the [`Makefile`](Makefile): `make install`, `make lint`, `make type`, `make test`, `make eval`, `make run QUERY=...`.

## The Risk Guardian (`langley_risk`)

Given a Solana token (mint address or symbol/pair), it fetches live market data and returns a structured `TokenRiskReport`: a verdict (`likely_safe` / `caution` / `likely_unsafe` / **`abstain`**), a calibrated confidence, and risk signals where **every claim cites the exact data field it came from**. If evidence is insufficient, it **abstains** rather than guessing — because this is financial-stakes software and a confident wrong "safe" verdict is the only fatal error.

See [`packages/langley_risk/README.md`](packages/langley_risk/README.md) for details.

## License

TBD.
