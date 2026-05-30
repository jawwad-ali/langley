# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Langley** is a multi-agent crypto-intelligence monorepo ("your private crypto intelligence agency"). It is built **one agent at a time, risk-first**: the only implemented agent is the **Risk Guardian** (`packages/langley_risk`), which assesses whether a Solana token is a scam. The other six agents and the `apps/api` (FastAPI) / `apps/web` (Next.js) are placeholder dirs (READMEs only). Read `docs/architecture.md` for the full vision and the rationale for building the highest-stakes, most-provable agent first.

The guiding principle: **trust is the product.** A confident wrong "safe" verdict is the only unforgivable error. Design decisions favor abstaining and deterministic safety nets over cleverness.

## Commands

This is a **uv workspace**. Python is not on PATH on the dev machine — always go through `uv run`. There is a `Makefile`, but on Windows without `make`, use the raw `uv` commands below.

```bash
uv sync                              # install everything (provisions Python 3.12 + all deps)
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run pyright                       # strict type check (must stay at 0 errors)
uv run pytest -m "not live"          # offline tests — no network, no OpenAI spend (this is what CI runs)
uv run pytest -m live                # live tests — real DexScreener + OpenAI (needs OPENAI_API_KEY)
uv run pytest packages/langley_risk/tests/unit/test_postprocess.py::TestDangerOverride   # single test class
uv run python -m langley_risk "<mint-or-symbol>"   # run the agent live (needs OPENAI_API_KEY)
uv run python -m langley_risk.evals.run            # v1 eval: free deterministic baseline (no OpenAI)
uv run python -m langley_risk.evals.run --live     # v1 eval: real GPT-4o agent
uv run python -m langley_risk.evals.run_v2         # v2 eval: real-token dataset, visibility-aware (live)
```

`uv sync` works because the root `pyproject.toml` *depends on* the member (`cipher-risk`/`langley-risk`) via `[tool.uv.sources]`. New implemented packages must be added both as a workspace member and as a root dependency or they won't install.

## Architecture: the Risk Guardian data flow

The package uses src-layout (`packages/langley_risk/src/langley_risk/`) with a strict one-direction flow. To understand it you must read across these layers:

```
providers/ → tools/ → agents/ → service/analyze.py → service/postprocess.py (gate)
   (data)     (LLM     (the      (orchestration)       (authoritative override)
              tool)    agent)
```

- **`domain/`** — pure Pydantic models, no I/O. `market.py:MarketSnapshot` is the provider-neutral **input** (has a `chain` field; null fields mean *unknown*, which is load-bearing — the agent must abstain on unknowns). `report.py:TokenRiskReport` is the agent's structured **output** contract (`output_type` for the SDK); its validators are trust-layer B.
- **`providers/`** — `base.py:DataProvider` is a `Protocol`. `DexScreenerProvider` is the only live one; `factory.get_provider()` selects it. **Adding a chain/source = a new provider behind this Protocol; the agent and gate never change.** Provider failures map onto the `errors.py` `ProviderError` hierarchy so the agent can distinguish "not found" from "source down."
- **`tools/market_tools.py`** — thin `@function_tool` wrappers. They read the provider from `RunContextWrapper[RiskDeps].context` (the DI seam in `agents/context.py`) — nothing imports a concrete provider. On failure they return `"DATA_UNAVAILABLE: ..."` so the model routes to abstain instead of hallucinating.
- **`agents/risk_guardian.py`** — builds the `Agent` (model, tools, `output_type`). `prompts.py` holds versioned instructions (bump `PROMPT_VERSION` on change).
- **`service/analyze.py:analyze_token()`** — the entrypoint used by CLI/API/evals. It wraps the provider in a `_RecordingProvider` so the agent and the gate see the **exact same snapshot** from one fetch.
- **`service/postprocess.py:apply_gate()`** — the **authoritative deterministic gate** (no LLM). It can override the agent and is the most important file for trust.

### The 3-layer trust design (defense-in-depth)

No single failure can produce a confident wrong "safe":
- **A — prompt** (`prompts.py`): must cite evidence; abstain under uncertainty; clear danger patterns → flag unsafe (don't abstain).
- **B — schema validators** (`report.py`): a conclusive verdict must carry evidence; an abstain must carry a reason.
- **C — gate** (`postprocess.py`): runs in this order and *overrides* the agent — (1) **danger override** forces `LIKELY_UNSAFE` on hard rug/honeypot patterns the agent missed; (2) **evidence integrity** forces `ABSTAIN` if a cited field wasn't actually in the snapshot; (3) **coverage** forces `ABSTAIN` if "likely_safe" lacks positive evidence (deep liquidity + age + two-sided trading); (4) **calibration** clamps confidence.

When you change gate thresholds or the prompt's danger rules, update both together (they mirror each other) and re-run the evals.

## Evals

Two harnesses, both important:
- **v1 (`evals/run.py`)** — synthetic golden set (`evals/datasets/golden_v1.jsonl` + `evals/fixtures/`). Default mode scores a **deterministic baseline** (free, the quality floor the LLM must beat); `--live` runs the real agent. Proves the *machinery*.
- **v2 (`evals/run_v2.py`)** — **real Solana tokens** (`evals/golden_v2/`). Built by the labeling pipeline in `scripts/` (`gather_candidates.py` → `label_candidates.py` → adversarial dual-skeptic audit → `assemble_v2.py`). It reports **visibility-aware**: each unsafe token is tagged `dexscreener_visible` (agent should catch) or `contract_only` (agent should *abstain* — the danger is invisible to DexScreener). The headline metric is **fatal-error count** (true-unsafe called `LIKELY_SAFE`), which must be 0.

Key real-world lesson baked into v2: most real Solana scam danger (creator-rug-history, mint/freeze authority, holder concentration) is **contract-only**, so a DexScreener-only agent correctly abstains. This is why the next planned step is a **Helius/RugCheck contract-data provider**. Also: **RugCheck risk flags are noisy** (they fire on legit majors), so labels are never assigned from them alone — and all golden_v2 labels remain provisional pending human review.

## Non-obvious gotchas

- **`.env` and OpenAI:** pydantic-settings reads `.env` only for `LANGLEY_RISK_*` settings — it does **not** export to `os.environ`, and `uv run` doesn't auto-load `.env`. The OpenAI SDK reads `OPENAI_API_KEY` from `os.environ`, so process entrypoints call `config.load_env_file()` (python-dotenv) first. Any new entrypoint that runs the live agent must do the same.
- **OpenAI Agents SDK:** package is `openai-agents` (pinned `>=0.17`); the import root is **`agents`**, not `openai_agents`. `output_type` does not disable tools — the loop calls tools then emits the structured final turn.
- **Ruff `TCH` is intentionally disabled** (see root `pyproject.toml`): with `from __future__ import annotations`, moving Pydantic/dataclass field types into a `TYPE_CHECKING` block breaks runtime model resolution. `RUF001/2/3` are ignored (em dashes are intentional).
- **Determinism:** evals call `observability.tracing.disable_tracing()`; the LLM is nondeterministic even at `temperature=0`, so don't expect bit-identical eval numbers run-to-run.
- **Windows console:** non-ASCII prints (em dash, `·`) can crash with a cp1252 `UnicodeEncodeError` — prefix scripts that print Unicode with `PYTHONIOENCODING=utf-8`, or stick to ASCII output.
- **Pyright strict + Pydantic default factories:** use a named typed factory (e.g. `Field(default_factory=_no_signals)`), not `default_factory=list` (infers `list[Unknown]`).

## Conventions

- Default branch is `main`. Keep Ruff, Pyright (strict), and `pytest -m "not live"` green before committing — CI (`.github/workflows/ci.yml`) runs exactly those plus the baseline eval.
- Tests are split: `tests/unit` (hermetic; LLM faked via monkeypatching `Runner.run`, providers via `respx`/recorded fixtures), `tests/integration` (`@pytest.mark.live`, skipped by default), `tests/eval`.
- The brand prefix is `langley_` (renamed from `cipher_`); keep package/module names consistent if adding agents.
