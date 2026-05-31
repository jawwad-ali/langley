# langley_onchain — On-Chain Forensics Agent

The second Langley agent: given a Solana token, it produces a **neutral, evidence-cited
forensic profile** of its on-chain and market footprint — *not* a safety verdict.

## Why it's distinct from the Risk Guardian

- **Risk Guardian** = a *judge*: it issues a verdict (`likely_safe` / `caution` / `likely_unsafe` / `abstain`).
- **On-Chain Forensics** = an *investigator*: it reports neutral facts across dimensions
  (liquidity, holders, authorities, activity, age), each citing the data field it came
  from, and **never** labels the token safe or unsafe. A future Synthesis orchestrator
  combines both.

## How it reuses the proven pattern (no new infrastructure)

It depends on `langley_risk` as a library and **reuses its providers** (DexScreener +
optional Helius enrichment), `MarketSnapshot`, `Evidence`, config, and observability —
without modifying the Risk Guardian. The flow mirrors it:

```
providers (reused) → tools → agent → service/analyze → service/postprocess (integrity gate)
```

The integrity gate is simpler here (no verdict): it just drops any finding that cites a
field not actually present in the data, keeping every surviving observation grounded.

## Usage

```bash
uv run python -m langley_onchain "So11111111111111111111111111111111111111112"
uv run python -m langley_onchain "<mint>" --json
```

Needs `OPENAI_API_KEY`; set `LANGLEY_RISK_PROVIDER=composite` + `LANGLEY_RISK_HELIUS_API_KEY`
to include contract-level findings (authorities, holder concentration).

## Tests

```bash
uv run pytest packages/langley_onchain/tests -q
```

> Note: provider/config/Evidence are reused from `langley_risk` for now. When a third
> agent arrives, those shared primitives will likely move to a `langley_core` package.
