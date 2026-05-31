# Langley — Interview Q&A Cheat-Sheet

Likely interview questions about this project, with short, confident answers in plain
English. Pair this with the [README](README.md) (the full walkthrough). Skim the **bold
one-liners** for a fast refresher before a call.

---

## A. The basics

**Q: In one sentence, what is Langley?**
A team of AI agents that checks whether a Solana crypto token is a scam and explains its
answer with evidence — a "private crypto intelligence agency."
> **One-liner:** *"It's a multi-agent AI that gives an evidence-backed risk verdict on a crypto token in seconds."*

**Q: What problem does it solve?**
Crypto (especially cheap Solana memecoins) is full of scams — *rug pulls* (creators drain
the money) and *honeypots* (you can buy but can't sell). People lose real money, and
checking by hand is slow and needs expertise. Langley does that homework instantly.

**Q: Who is it for?**
Retail crypto traders hunting early tokens — with an emphasis on emerging markets like
Pakistan where crypto adoption is high. It's a portfolio project showcasing multi-agent AI
engineering.

**Q: Is it live / handling real money?**
No — it's a working demo and showcase. It produces **risk signals, not financial advice**,
and I'm deliberately honest that it isn't production-grade for real money yet (see the
evaluation answers).

---

## B. "Why multi-agent?" (the most likely question)

**Q: Why a team of agents instead of one big prompt?**
Three reasons:
1. **Separation of concerns** — each agent has one clear job, so each is easier to test and trust.
2. **Different roles need different rules** — a *judge* (gives a verdict) and an *investigator* (reports neutral facts) shouldn't be the same prompt; mixing them muddies both.
3. **It matches the product idea** — "an intelligence agency" of specialists that cross-check each other.
> **One-liner:** *"One prompt doing everything is hard to trust or test. Splitting it into a judge, an investigator, and an editor makes each piece simple, testable, and independently correct."*

**Q: What are the agents?**
- **Risk Guardian** — the *judge*: outputs a verdict (safe / caution / unsafe / not-sure).
- **On-Chain Forensics** — the *investigator*: neutral factual profile, **no verdict**.
- **Synthesis Orchestrator** — the *editor*: runs both and fuses them into one report.

**Q: How do they "collaborate"?**
The orchestrator runs the judge and investigator **at the same time**, then a third AI
fuses their outputs into one briefing — with a cross-analysis of whether the two agents'
pictures agree.

---

## C. Trust & safety (the heart of the project)

**Q: How do you stop the AI from hallucinating / making things up?**
Three independent layers ("defense in depth"):
1. **Prompt** — every claim must cite a real data field and value; if data is missing, abstain.
2. **Schema validation** — a real verdict must carry evidence; an abstain must carry a reason (enforced by code, not trust).
3. **A deterministic safety gate** — plain (non-AI) code that re-checks the AI's answer and can **override** it.
> **One-liner:** *"The AI proposes; deterministic code disposes. Every claim must cite data, and a non-AI gate can override the AI — only ever toward the safer answer."*

**Q: What exactly does the gate do?**
- Forces **unsafe** on obvious scam patterns the AI missed (e.g. near-zero liquidity).
- Forces **abstain** if the AI cited a field that wasn't actually in the data ("ungrounded").
- Won't let "likely safe" through without real positive evidence.
- It **never** moves a verdict toward a more confident "safe" — only toward caution.

**Q: Why is "abstain" (not-sure) so important?**
Because the one unforgivable error is telling someone a scam is "safe." Saying "I'm not
sure" is a perfectly good, honest answer that protects the user. The whole system prefers
abstaining over guessing.

**Q: In the orchestrator, can the fusing AI change the verdict?**
**No — by design.** The final verdict is copied **verbatim** from the Risk Guardian. The
fusing AI's output type literally has no verdict field, so it *cannot* decide or soften the
safety call — it only writes the narrative around it.

---

## D. AI / agent specifics

**Q: Why GPT-4o and the OpenAI Agents SDK?**
GPT-4o is a strong, widely-available model. The Agents SDK gives me two things cleanly:
**tools** (the agent can call a function to fetch live data) and **structured output** (it
returns validated JSON matching my schema, not free text I'd have to parse). The model is
behind a config setting, so swapping to a newer one is a one-line change.

**Q: How does "structured output" work here?**
I define a Pydantic model (e.g. `TokenRiskReport`) and pass it as the agent's `output_type`.
The SDK forces the model to return JSON that fits that shape, and Pydantic validates it.
Bad output is rejected before it reaches my code.

**Q: temperature / determinism?**
I run at temperature 0 for consistency, but LLMs still vary slightly run-to-run — so I never
claim bit-identical results, and the deterministic gate is what guarantees the safety rules.

---

## E. Data & providers

**Q: Where does the data come from?**
Two free sources behind one common interface:
- **DexScreener** — market data (price, liquidity, trading, age) — the "outside view."
- **Helius** — contract data (can the creator mint more coins? who holds it?) — the "inside the kitchen" view.

**Q: Why two sources — what did Helius add?**
On real tokens, most scam danger is **invisible from market data alone** — it's in the
contract. Helius lets the agent *see inside*, which moved it from "I'm not sure" to actually
catching contract-level scams.

**Q: How hard is it to add a new data source or blockchain?**
Easy — that's the point of the design. Every source implements one `DataProvider` interface,
so adding Helius (or later Ethereum) is **a new provider with zero changes to the agents or
the gate**.
> **One-liner:** *"New chain or source = one new provider behind an interface. The brain doesn't change."*

---

## F. Evaluation (your best "judgment" story)

**Q: How do you know it actually works?**
With evals, not vibes. I built three layers of tests:
1. A **synthetic** baseline (proves the machinery).
2. A **real-token** set, labeled using multiple sources and an adversarial audit.
3. A **real, outcome-verified, held-out** set — tokens labeled by *what actually happened to
   them*, that the agent was never tuned on.

**Q: What's the headline result — and the honest caveats?**
On the blind held-out set: **F1 ≈ 0.94, precision 1.0, and zero fatal errors** (never called
a dead token "safe"). Caveats: the set is small (~18 test tokens), memecoin-skewed, and
labels are rule-based — so it's a strong signal, not a production guarantee.

**Q: Tell me about a time your tests misled you.** *(great story)*
Early tests on made-up data scored 100%, which lulled me. When I built a **real held-out**
test, the honest score was **0.63** — the agent was **over-warning on healthy tokens**. I
diagnosed it (it treated "holder concentration" as a scam signal, but that number usually
includes exchange/pool wallets), fixed the instructions on a *training* split, and
re-measured *once* on the blind set → **0.94**.
> **Takeaway:** *"Perfect scores on data you made up are a red flag, not a green light."*

**Q: Why tune on "train" and measure on "test"?**
So I'm not grading my own homework. If I tuned and tested on the same tokens, a high score
would just mean memorization. Keeping the test set blind makes the number honest.

---

## G. Engineering quality

**Q: How is the codebase organized?**
A **monorepo** (uv workspace) with one small package per agent plus a demo app. Every agent
uses the same internal layout (data → tools → agent → service → gate), so once you learn one,
you understand them all.

**Q: How do you keep quality high?**
Linting (Ruff), **strict type-checking** (Pyright at zero errors), and tests (pytest) stay
green at every commit, enforced in CI. The agents' "machinery" is tested offline with the
LLM faked, so tests are fast, free, and deterministic.

**Q: You said "no breaking changes" a lot — how did you guarantee it?**
When I added agents 2 and 3, they **depend on** the first package and reuse it as a library
— I never edited the working code. The proof: the original agent's full test suite kept
passing the whole time (49 tests total now).

**Q: Did you use any review process?**
Yes — after building each agent I ran an **adversarial review** (independent checks for
breaking changes, correctness, and robustness) before committing. It repeatedly caught real
bugs early — e.g. a way the fusing AI could imply "safe" in its wording.

---

## H. Trade-offs & decisions

**Q: Biggest design decision?**
**Risk-first:** fully build and prove the highest-stakes agent before adding breadth, rather
than half-building all seven. It's slower to "look complete" but every shipped piece is
trustworthy.

**Q: A trade-off you accepted?**
The orchestrator runs both agents separately, so it fetches data twice (more API calls). I
accepted that for simplicity at demo scale; sharing one fetch is a future optimization.

**Q: Something you deliberately did NOT do?**
I skipped a couple of reviewer suggestions on purpose because they'd cause harm — e.g. one
would have broken the AI's strict-JSON mode, another would have required editing the working
first package. Knowing what *not* to change is part of the job.

---

## I. Scaling & production

**Q: Could this serve 100k users? What's missing?**
The architecture scales (stateless, swappable providers), but for real users with real money
I'd add: a much larger, **human-verified** dataset; **shadow mode** (log live verdicts, check
later what actually happened) to keep improving safely; calibrated confidence; caching and
rate-limiting (basic rate-limiting already exists); and clear legal framing.
> **One-liner:** *"It's demo-ready, not money-ready — and I can tell you exactly what the gap is."*

**Q: How would you measure success in production?**
Not by "did users make money" (that's noisy and the wrong signal for a *risk* tool) — but by
**outcomes**: of the tokens we judged, what actually happened? The fatal-error rate (a scam
called safe) must stay at zero.

---

## J. Future improvements

- Finish the agent team (4 more: Narrative, Sentiment, Simulator, Storyteller) — they need new data like the X/Twitter API.
- Extract shared code into a `langley_core` package (reduce duplication across agents).
- Bigger human-reviewed dataset + shadow mode + calibrated confidence.
- Deploy a public demo URL; add multi-chain support (just new providers).

---

## K. Quick-fire facts (memorize these)

- **Stack:** Python 3.12 · OpenAI Agents SDK + GPT-4o · Pydantic · FastAPI · DexScreener + Helius · uv / Ruff / Pyright / pytest.
- **Agents built:** 3 of 7 (Risk Guardian, On-Chain Forensics, Synthesis Orchestrator).
- **Held-out result:** F1 ≈ 0.94, precision 1.0, **0 fatal errors**.
- **Core principle:** never tell a user a scam is "safe" — prefer "not sure."
- **Trust design:** prompt + schema validation + a deterministic gate that can override the AI.
- **Tests:** 49 passing, Pyright strict at 0, all green in CI.
