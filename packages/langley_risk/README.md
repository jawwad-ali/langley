# langley_risk — Risk Guardian

Evidence-cited Solana token risk assessment, built on the **OpenAI Agents SDK** (GPT-4o). Given a mint address or symbol, it fetches live market data and returns a structured `TokenRiskReport`.

This is the first agent in [Langley](../../README.md) — deliberately built first because it is the highest-stakes and the only one with hard ground truth (see [`docs/architecture.md`](../../docs/architecture.md)).

## What makes the output trustworthy

Trust is enforced at three independent layers, so no single failure yields a confident wrong "safe":

1. **Prompt** — every signal must cite a concrete data field; missing data → abstain.
2. **Schema validators** ([`domain/report.py`](src/langley_risk/domain/report.py)) — a conclusive verdict must carry evidence; an abstain must carry a reason.
3. **Deterministic gate** ([`service/postprocess.py`](src/langley_risk/service/postprocess.py)) — an LLM-free pass that verifies every cited field actually existed in the data, enforces coverage rules for "likely_safe", and **forces abstain** on any violation. It also calibrates confidence.

The free DexScreener source cannot see holder distribution or mint/freeze authority, so those snapshot fields are `None` — and the gate will not let the agent call a token "safe" on market data alone.

## Layout

```
src/langley_risk/
  domain/      Pydantic models + enums (input MarketSnapshot, output TokenRiskReport)
  providers/   DataProvider Protocol + DexScreener client (+ factory)
  tools/       @function_tool wrappers
  agents/      Agent definition, prompts, run-context DI
  service/     analyze_token() + the deterministic gate
  observability/ structlog logging + SDK tracing bridge
  evals/       golden dataset loader, metrics, baseline, harness
evals/         golden_v1.jsonl + recorded snapshot fixtures
tests/         unit / integration (live) / eval
scripts/       record_fixtures.py
```

## Usage

```bash
# From the repo root (uv workspace):
uv run python -m langley_risk "So11111111111111111111111111111111111111112"   # live (needs OPENAI_API_KEY)
uv run python -m langley_risk.evals.run        # baseline eval (free, no OpenAI)
uv run python -m langley_risk.evals.run --live # real-agent eval (needs OPENAI_API_KEY)
```

## Tests

```bash
uv run pytest -m "not live"   # unit + offline eval (no network, no OpenAI)
uv run pytest -m live         # live DexScreener / OpenAI checks
```

## Extending to new data sources

Implement the [`DataProvider`](src/langley_risk/providers/base.py) protocol (e.g. a Helius or Birdeye client) and add a branch in [`providers/factory.py`](src/langley_risk/providers/factory.py). Tools and the agent need no changes — they only know the protocol.
