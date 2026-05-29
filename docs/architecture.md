# Langley — Architecture & Roadmap

## What we're building

Langley is a multi-agent AI system that acts as a "personal crypto intelligence agency." The end-state vision (see [`../CONCEPT.md`](../CONCEPT.md)) is seven specialist agents that monitor on-chain data, social chatter, and market psychology, then collaborate, debate, and cross-verify before producing ranked, evidence-cited intelligence with confidence scores.

This document explains **how we get there** — and, crucially, the order.

## Guiding principle: risk-first, eval-driven, breadth last

The most common way a system like this dies is **building breadth before proving the risky core**: wiring up all seven agents + orchestration + a dashboard, demoing it on a cherry-picked token, and then having it confidently tell a real user that a honeypot is "safe." Because this is financial-stakes software, **trust is the product**, and a confident wrong "safe" verdict is the only truly fatal error.

So we invert the usual order:

1. **Prove the riskiest assumption first.** Can a single agent produce a trustworthy, non-hallucinated, evidence-cited verdict on real data? We answer this with the **Risk Guardian** (`packages/langley_risk`).
2. **Make it measurable from day one.** The first deliverable isn't the agent — it's the **eval harness + golden dataset** that measures precision/recall on the "unsafe" verdict. "It works" is meaningless without that.
3. **Establish a reusable pattern.** The Risk Guardian's structure (domain models → provider abstraction → tools → agent → deterministic post-process gate → evals) becomes the template every later agent copies.
4. **Add breadth only after the bar is met.** The other six agents and the orchestration/debate loop come after — each one repeating a proven pattern instead of inventing it seven times.

## Why the Risk Guardian goes first (not On-Chain Forensics or the Orchestrator)

- It is the **trust anchor** — its mistakes are the ones that cost users money.
- It is the **only agent with hard ground truth** — a token either rugged or it didn't; a contract is or isn't a honeypot. That means we can *actually build evals*, which is impossible for fuzzy agents like "Narrative Scout."
- Much of its value is **rules + data** (liquidity locked? mint authority renounced? holder concentration?) with the LLM doing *synthesis*, not invention — which structurally suppresses hallucination.

## The seven agents (target state)

| # | Agent | Package | Job | State |
|---|-------|---------|-----|-------|
| 1 | Risk Guardian | `langley_risk` | Rugs, honeypots, malicious contracts, portfolio risk | ✅ Built |
| 2 | On-Chain Forensics | `langley_onchain` | Transactions, wallets, liquidity, contracts | 🅿️ Placeholder |
| 3 | Narrative Scout | `langley_narrative` | Emerging trends on X, Telegram, communities | 🅿️ Placeholder |
| 4 | Sentiment & Psychology | `langley_sentiment` | Crowd emotion, whale activity, FOMO/FUD | 🅿️ Placeholder |
| 5 | Opportunity Simulator | `langley_simulator` | Market simulations & probability scenarios | 🅿️ Placeholder |
| 6 | Synthesis (Orchestrator) | `langley_synthesis` | Merges everything into ranked insights | 🅿️ Placeholder |
| 7 | Storyteller | `langley_storyteller` | Turns technical data into shareable narratives | 🅿️ Placeholder |

## The reusable agent-package pattern

Every agent package uses [src-layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) and the same internal layering (separation of concerns, each file one responsibility):

```
domain/        Pure Pydantic models + enums. No I/O. The input snapshot and the
               output report contract. This is what everything else agrees on.
providers/     Provider-abstracted data clients behind a DataProvider Protocol.
               Swap DexScreener → Helius/Birdeye with zero changes upstream.
tools/         Thin @function_tool wrappers exposing provider methods to the agent.
agents/        The Agent definition (model, tools, structured output) + versioned
               prompt templates + a RunContext dependency-injection dataclass.
service/        analyze_*()  — the high-level entrypoint used by CLI/API/tests.
               postprocess  — an AUTHORITATIVE, LLM-free gate (see below).
observability/ Structured logging + a tracing processor.
evals/ + tests/ A golden dataset and a first-class eval harness.
```

### Trust = defense-in-depth (three layers)

The thing that makes the output trustworthy is enforced at three independent layers, so no single failure produces a confident wrong answer:

- **A — Prompt (behavioral):** every risk signal must cite a concrete data field + value; missing data → the agent must **abstain**, never guess.
- **B — Schema validators (structural):** a non-abstain verdict must carry evidence; confidence ∈ [0,1]; abstain must carry a reason. Malformed output is rejected.
- **C — Deterministic post-process (authoritative, no LLM):** independently verifies that every cited field actually exists in the data the agent saw, enforces coverage rules, and **forces abstain** on any violation. It also maps the LLM's self-reported confidence through a deterministic calibration function (the LLM's confidence is treated as untrustworthy).

## Technology choices

| Concern | Choice | Notes |
|---------|--------|-------|
| Agent framework | **OpenAI Agents SDK** (`openai-agents`) | `Agent` + `Runner` + `@function_tool`; structured output via `output_type` |
| LLM | **GPT-4o** | Behind config (`LANGLEY_RISK_MODEL`) — one-line swap to a newer model |
| First data source | **DexScreener** (free) | Behind a `DataProvider` Protocol; Helius/Birdeye drop in later |
| Tooling | **uv · Ruff · Pyright (strict) · pytest** | One shared config at the monorepo root |
| Backend (future) | FastAPI · Supabase | `apps/api` — thin layer over agent packages |
| Frontend (future) | Next.js 15 · Tailwind · shadcn/ui · Recharts | `apps/web` — talks only to the API |

## What is explicitly deferred

The other six agents (code), the debate/orchestration loop, the FastAPI backend, the Next.js frontend, Supabase/auth, the vector DB for narrative memory, PDF export, fitted (vs. clamped) confidence calibration, and a fully-curated golden dataset. Each has a placeholder home and will follow the proven `langley_risk` pattern once the core eval bar is met.
