# langley_synthesis — Synthesis / Orchestrator Agent

The agent that makes Langley a *team*: it runs the specialist agents, then fuses their
outputs into one unified, ranked **IntelligenceReport**.

## What it does

```
            ┌─ Risk Guardian   (verdict + signals) ─┐
 token ──►  │  (run concurrently)                   ├─► Synthesis LLM ─► IntelligenceReport
            └─ On-Chain Forensics (neutral profile) ┘   (narrative + cross-analysis)
```

Output combines: the **headline**, a **briefing**, an **agreement** assessment (do the
specialists corroborate, conflict, or is the picture mixed?), ranked **key points**, plus
the underlying signals and findings for provenance.

## The trust guarantee (why the orchestrator can't weaken safety)

The report's **`verdict` and `confidence` are carried VERBATIM from the Risk Guardian.**
The synthesis LLM produces *only* narrative and cross-analysis (`SynthesisOutput` has no
verdict field), and the orchestrator assembles the final report — so the LLM **cannot
decide or soften the safety call.** The synthesizer is also told the verdict is
authoritative and instructed to stay consistent with it.

If On-Chain Forensics fails, the orchestrator **degrades gracefully** (the verdict is
essential; the profile is supporting). If the Risk Guardian fails, that is a hard error.

## How it reuses everything (no breaking changes)

Depends on `langley_risk` and `langley_onchain` and orchestrates their public entrypoints
(`analyze_token`, `analyze_onchain`) — editing neither.

## Usage

```bash
uv run python -m langley_synthesis "So11111111111111111111111111111111111111112"
uv run python -m langley_synthesis "<mint>" --json
```

Needs `OPENAI_API_KEY`; set `LANGLEY_RISK_PROVIDER=composite` + `LANGLEY_RISK_HELIUS_API_KEY`
for contract-level depth.

> Note: shared primitives (providers, `Evidence`, the recording wrapper) are still reused
> from `langley_risk`. With three agents now built, extracting them into a `langley_core`
> package is the natural next refactor.
