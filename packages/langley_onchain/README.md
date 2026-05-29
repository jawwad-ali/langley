# langley_onchain — On-Chain Forensics Agent (placeholder)

> 🅿️ **Not implemented yet.** This is a reserved home in the monorepo.

**Job:** Analyze transactions, wallets, liquidity, and smart contracts on-chain.

This agent will be built **after** the Risk Guardian (`langley_risk`) clears its eval bar, and it will follow the exact same proven pattern:

- `domain/` — pure Pydantic models (provider-neutral I/O contracts)
- `providers/` — provider-abstracted data clients behind a `DataProvider` Protocol
- `tools/` — thin `@function_tool` wrappers
- `agents/` — the agent definition + versioned prompts
- `service/` — a top-level entrypoint + an authoritative deterministic post-process gate
- `evals/` + `tests/` — a golden dataset and a first-class eval harness

See [`packages/langley_risk`](../langley_risk) for the reference implementation and [`docs/architecture.md`](../../docs/architecture.md) for the roadmap.
