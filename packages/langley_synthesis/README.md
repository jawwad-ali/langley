# langley_synthesis — Synthesis / Orchestrator Agent (placeholder)

> 🅿️ **Not implemented yet.** This is a reserved home in the monorepo.

**Job:** Combine all agents' findings into clear, ranked insights with confidence scores. This is the orchestrator that runs the debate/cross-verification loop between the specialist agents.

Built **last**, once the specialist agents (Risk Guardian first) each clear their eval bars. It will orchestrate the others rather than fetch data directly, so its design differs slightly — but it still ships with its own `evals/` measuring end-to-end ranking quality.

See [`packages/langley_risk`](../langley_risk) for the reference implementation and [`docs/architecture.md`](../../docs/architecture.md) for the roadmap.
