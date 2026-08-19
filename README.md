# Alpaca AI Trading Agents Hackathon — Planning

> Master plan for the lablab.ai × Alpaca "AI Trading Agents" hackathon.
> Living document — update as decisions change.

---

## 1. Context & goal

- **Event:** lablab.ai — Alpaca AI Trading Agents Hackathon
- **Dates:** **Aug 28 – Sep 4, 2026** (7 days online; kickoff Fri Aug 28, 8:30 PM IST). **Live trading window ≈ 5–6 market days only.**
- **Prize pool:** $5,000 ($2,500 / $1,500 / $1,000). Paid to individuals (designate one on a team). Teams 1–6.
- **Goal:** Build an autonomous options-trading agent that stands out from the crowd, not a "read news → buy call" toy.
- **Constraint (updated):** No paid Claude/OpenAI key and no sponsor credits (AMD credit was a typo). **But** Yugo has **~$100 in winnings** from a previous hackathon earmarked for **Hugging Face Inference Providers** — so we can now run **paid HF-hosted open models** (e.g. Kimi-K3, DeepSeek-V4-Pro) instead of being locked to free tiers. Free tooling remains the fallback; the paid budget is a bonus, not a dependency.

**Core requirements (mandatory, from the rules):**
1. **Autonomous AI trading agent** using Alpaca's Trading API.
2. **Must use Alpaca's MCP server OR CLI.** ✅ (we use MCP + CLI)
3. **All strategies must incorporate options trading.** ✅ (calls/puts) — Alpaca options are enabled by default on paper accounts.

---

## 2. Track decision

**Chosen: Track 1 — Options Alpha Agents** (directional call/put agents with a testable thesis).

| Track | Why / why not |
|-------|---------------|
| **1. Options Alpha** ✅ | Simplest options plumbing (single-leg), and the track literally rewards *reasoning/conviction* — plays to LLM + RAG strengths. Best live-demo story. |
| 2. Volatility & Event | Higher ceiling (trade IV not direction), but concept-risk (implied vol/greeks). Stretch option only. |
| 3. Hedging & Risk | Defensive, rules-driven; medium options complexity. |
| 4. Income & Overlay | Mechanical wheel/covered calls; "consistency" is hard to demo in a short window. |

**Winning insight:** most teams will ship a coin-flip dressed up with an LLM. Our moat is the **decision *process*** — a multi-signal, options-aware engine that scores conviction, sizes by risk, picks the right contract, and grades its own thesis.

---

## 3. Model / brain decision

**Now leaning paid-HF for the deep-thinking brain** (Yugo's ~$100 HF budget) — a stronger reasoning model with real rate limits beats juggling free-tier caps.

> **Why bigger = better here (Yugo):** SOTA large models are markedly stronger at **agentic tool-use** (planning multi-step tool calls, staying on-task across a wake cycle) and carry deeper **finance/markets knowledge** (options mechanics, greeks, market structure) baked in. For a thesis-forming trading agent, that's exactly the capability we're paying for — the reasoning *is* the product.

- **Primary brain (planned):** a top open model on **Hugging Face Inference Providers** — candidates: **Kimi-K3**, **DeepSeek-V4-Pro** (final pick TBD, Chirag skimming the [supported-models list](https://huggingface.co/inference/models)). Paid but funded, so higher rate limits and no 1M-token/week ceiling to design around. **Cost is a non-issue — see §13a** (~$2–20 total vs. Yugo's ~$100).
- **Free-tier fallback / cost saver:**
  - **Gemini** (Google AI Studio free tier — strong reasoning, huge context for RAG) — still viable if we want to preserve HF budget.
  - **Groq** (Llama 3.3 70B — ultra-fast) for cheap high-frequency steps like headline sentiment.
- **Swappable** via LangChain — the provider is one `.env` edit / one adapter swap, so each teammate can run a *different* brain on their own account for the bake-off (see §14a).
- **Decision style:** **Hybrid** — LLM forms the thesis; deterministic code enforces risk and executes. Judges reward visible guardrails; a pure-LLM order-placer reads as reckless.

> **Rate-limit safeguard:** if we end up on a free/limited tier for any provider, add **exponential-backoff retry** around every LLM call (e.g. on HTTP 429: wait, retry, don't crash the wake cycle). A paid HF key largely removes this need, but the funnel already batches calls so a stray 429 shouldn't kill a run.

---

## 4. Architecture

```
   News / price signals  ─────┐   (RAG layer)
                              ▼
                 ┌─────────────────────────┐
                 │   Gemini brain (agent)   │  reasons → forms thesis
                 │   LangChain / LangGraph  │  → decides call/put + size
                 └───────────┬─────────────┘
                             ▼
                 ┌─────────────────────────┐
                 │   Risk guardrail layer   │  our code: position caps,
                 │   (we own this)          │  stop-loss, per-symbol limits
                 └───────────┬─────────────┘
                             ▼  approved trades only
          langchain-mcp-adapters ─► Alpaca MCP server ─► Alpaca paper account
                             │                             (options orders)
                             ▼
                   Alpaca CLI ── scheduled / cron "run every N min" mode
```

### Why MCP is central
The Alpaca Partners page states the **MCP server** is *"the core of the hackathon theme."* So we build **on top of Alpaca's MCP server** instead of hand-rolling a REST wrapper — this is an explicit judging signal.

### Component roles
- **Alpaca MCP server** (`github.com/alpacahq/alpaca-mcp-server`) — Python server run locally with paper keys. Exposes Alpaca functions as structured MCP tools (account, positions, quotes, option contracts, orders). We don't rebuild these.
- **`langchain-mcp-adapters`** — bridges the MCP server's tools into LangChain tools the **Gemini** agent can call. This is the key trick to use the sponsor's MCP server with a free non-Claude brain.
- **Risk guardrail layer (ours)** — the LLM gets **read** tools directly (quotes, positions, chains) but **NOT** the raw place-order tool. It calls our `propose_trade(thesis, symbol, direction, size)`; our code validates against risk rules, then calls the MCP execute tool. Auditable gate between "AI decided" and "money moved."
- **Alpaca CLI** — for long-running/scheduled runs (cron "wake every 15 min, re-evaluate thesis"). Lighter than keeping the full stack hot; the "production runtime" story for the demo.

---

## 5. The decision engine (the differentiator)

Combine signals into a transparent **conviction score (0–100)**; only trade above a threshold.

### Tier 1 — Directional conviction (from Alpaca stock bars + news endpoint)
- Trend — price vs. 20/50-day moving averages
- Momentum — RSI, MACD
- Volume — unusual / relative volume confirmation
- Multi-timeframe agreement — daily + intraday align
- Market regime — SPY risk-on/off (don't fight the tape)
- News/earnings sentiment (RAG) — one weighted input, not the whole thesis

### Tier 2 — Options-aware metrics (**the real edge — most teams skip these**)
- **Implied Volatility + IV Rank** — is the option expensive or cheap vs. its own past year?
- **Expected move** — market's priced-in move; is our thesis bigger than what we pay for?
- **Greeks** — Delta (directional exposure / prob-ITM proxy), Theta (daily decay "rent"), Vega (IV exposure)
- **Strike + expiry selection** — target delta (e.g. ~30Δ), DTE balances thesis timeframe vs. theta bleed
- **Liquidity gate** — open interest, volume, bid-ask spread; reject illiquid contracts
- **Break-even + risk/reward** — required move realistic?

### Tier 3 — Risk & portfolio metrics (quantified guardrails)

**Core principle:** you don't *predict* randomness (an Elon tweet, a shock headline) — you *size and structure* so it can't kill you.

**The structural shield — long options = defined risk.** When you **buy** a call/put, max loss = the premium paid. No margin call, no surprise debt. A bad overnight gap can only cost the premium you *chose in advance*. This is *why* the track uses long options — capped downside, big upside.

**Hard-coded risk config** (anchored to Alpaca paper default of $100k):
```python
STARTING_CAPITAL       = 100_000   # Alpaca paper default
MAX_RISK_PER_TRADE     = 0.02      # ≤ 2% → max $2,000 premium on any one trade
MAX_PORTFOLIO_DEPLOYED = 0.30      # ≤ 30% of account in open premium at once
MAX_PER_SYMBOL         = 0.05      # ≤ 5% in any single underlying (the "Elon cap")
MIN_CONVICTION         = 65        # don't trade below this scorecard number
STOP_LOSS              = -0.40     # exit a position down 40% of its premium
TAKE_PROFIT            = 0.75      # exit a position up 75%
DAILY_LOSS_HALT        = -0.05     # stop trading for the day if account down 5%
AVOID_EARNINGS_WITHIN  = 2         # days — skip naive bets right before earnings
```

**Rule → what it protects against:**
| Rule | Protects against |
|------|------------------|
| 2% max per trade | One surprise dents you ≤ 2%; can't blow up on a single bet |
| 5% max per symbol | Can't be secretly all-in on one name (TSLA tweet can't wreck the book) |
| 30% max deployed | 70% stays cash — dry powder + not fully exposed to market-wide shock |
| Stop-loss −40% | Auto-exit slow losers before they round-trip to zero |
| Daily loss halt −5% | Benches the agent on a brutal day; no revenge-trading |
| Avoid earnings | Dodges *scheduled* volatility bombs unless the thesis IS the event |

**Gap risk (be honest about it):** a stop-loss is **not** a force field. Between the ~15-min checks — and overnight — price can gap past the stop, so the agent exits at the (worse) open price. *Mitigant:* long options already cap loss at premium. So: stop-loss saves money on **slow** losers; **defined risk** saves you on **sudden** ones. Two layers.

**The calendar edge:** many "surprises" aren't random — earnings, Fed meetings, FDA decisions are on a calendar. The agent pulls the earnings calendar and refuses to hold a naive directional bet into a scheduled event. Removes a big chunk of miscellaneous risk for free; only the genuinely unpredictable remains — and sizing caps that.

**Portfolio-level checks:** net delta (avoid 5x the same bet), correlation check (don't stack correlated calls), max concurrent positions / sector concentration caps.

**Where it lives:** these rules ARE the risk-gate layer (the `propose_trade` wrapper). The LLM never sees or overrides them — it proposes; the gate (1) rejects if conviction < 65, (2) rejects if any cap is broken, (3) **sizes** premium ≤ 2%, (4) attaches stop-loss / take-profit, (5) then lets MCP place the order. → the "agent wanted 10 contracts, gate capped it at 2" demo moment.

### Recommended buildable set (don't over-scope)
> Tier 1 (3–4 signals) → **conviction score** → Tier 2 (**IV Rank + expected move + delta-based strike pick + liquidity gate**) → Tier 3 risk sizing → **self-grading log**. Add bull/bear debate if time allows.

---

## 6. Candidate selection funnel & token budget

**Core principle:** *Math is free. LLM tokens are precious. Filter with math, decide with the LLM.*
The LLM must **never** scan the market. A deterministic funnel narrows thousands of names to 2–3 finalists at zero token cost; the LLM only runs on the last mile.

Free-tier ceiling assumed: **~1M tokens per LLM per week.** This design stays well under it.

> **With the paid HF budget (§3), the hard weekly ceiling goes away** — but keep the funnel anyway. "Filter with math, decide with the LLM" isn't just about token caps; it keeps the ~$100 stretching across three teammates' test accounts and keeps each wake cycle fast/cheap. Paid ≠ license to let the LLM scan the market.

### The funnel
```
  ~5000 stocks
       │   ❌ LLM never touches this level
       ▼
  [1] Fixed watchlist        → ~20–40 liquid, optionable names            (0 tokens)
       ▼
  [2] Deterministic screen   → RSI / MACD / volume / regime in Python      (0 tokens)
       │                        keep only names with a real setup
       ▼
  2–3 candidates survive
       ▼
  [3] LLM thesis             → news + reasoning + bull/bear debate         (tokens ONLY here)
       ▼
  [4] Contract pick          → strike/expiry by delta + DTE math on chain  (0 tokens)
```

- **[1] Watchlist, not the market** — fixed ~20–40 liquid, heavily-optioned names (mega-caps + a few ETFs). Kills 99% of the cost instantly.
- **[2] Deterministic pre-screen** — Tier 1 signals are pure math on price bars → **0 LLM tokens**. Rank, keep only setups above a threshold (~2–3/day survive).
- **[3] LLM as closer, not scanner** — only the 2–3 survivors get expensive thesis reasoning / debate.
- **[4] Contract selection is math** — LLM decides direction + conviction; code picks the actual contract by target delta (~30Δ), DTE, tightest spread.

### Token savers
- **Use Alpaca's news endpoint, not web browsing** — structured, free, per-ticker; browsing is slow, unreliable, token-hungry.
- **Split providers** — Groq (own free budget) for cheap high-frequency bits (headline sentiment); Gemini for deep thesis. Two free budgets ≈ double the ceiling.
- **Cache + scheduled cadence** — run the funnel a few times/day (Alpaca CLI cron), cache news/results; don't re-query per thesis iteration.

### Weekly budget estimate
| Stage | LLM tokens |
|-------|-----------|
| Watchlist + Tier 1 screen (all names) | **0** |
| Thesis on ~3 finalists/day (~7k each) | ~21k/day |
| Bull/bear debate (×3) | ~40k/day |
| Contract selection | **0** |
| **Weekly total (~5 trading days)** | **~300k** — comfortably under 1M |

> Mental model: the LLM isn't a scanner, it's a **closer**. Math does the scouting; the LLM shows up only for the final 2–3 decisions.

---

## 7. Runtime & scheduling model

**Key correction:** the MCP server does **not** trade on its own. It's *hands, not a brain* — a translator that holds the Alpaca keys and exposes Alpaca functions as tools. It sits idle until the agent calls it. The **agent** (Gemini + funnel + risk gate) decides; the MCP executes.

```
  Agent (brain)  ──calls tools──►  MCP server (hands)  ──►  Alpaca account
  decides WHAT to do              translates & executes      holds positions
```

### "Runs 5–7 days" ≠ an LLM thinking 24/7
A **scheduler is the heartbeat.** It wakes the agent on a cadence; the agent runs one cheap cycle, then sleeps. Between wakes = **zero tokens, zero cost**; positions rest in the Alpaca account. Market is only open ~6.5 hrs/day, 5 days/week — nights/weekends the agent sleeps entirely. This is what keeps the weekly budget (~300k tokens) realistic.

```
  every 15–30 min during market hours:
     wake → run funnel (math, free) → LLM only if finalists → act via MCP → sleep
  overnight / weekend:
     sleep entirely (positions rest in Alpaca)
```

### The wake cycle (each tick)
1. **Rehydrate** — ask MCP "what do I hold?" + read local thesis log. (Agent is *stateless between runs*; it re-learns its situation each wake.)
2. **Manage open trades first** — check stop-loss / take-profit on existing positions; close via MCP if hit.
3. **Hunt new trades** — run Tier 1 funnel (math); spend LLM tokens only if a candidate survives.
4. **Act** — approved trades → risk gate → MCP places order.
5. **Log & sleep.**

### Where state / "memory" lives (survives crashes)
Two sources of truth, both **outside** the LLM:
- **Alpaca account** = the real positions (authoritative). Query fresh each wake via MCP.
- **Local log / DB** = theses + entry reasoning (for stop-loss tracking + self-grading).

Because the agent rehydrates from these every wake, a reboot/crash is harmless — restart the script and it resumes by reading account state. No fragile long-lived in-memory process.

### Deployment decision (laptop can't stay on → must run in the cloud)

Two runtime styles:
| Style | How it stays alive | Needs |
|-------|-------------------|-------|
| **A. Cron / scheduled** | Platform fires the script every N min; script runs one cycle and **exits** | No always-on machine — just a scheduler |
| **B. Always-on process** | One process runs a `while True: … sleep()` loop all week | A machine that never sleeps (cloud VM) |

**✅ Chosen: Style A on GitHub Actions (scheduled cron).** Free, no server, no laptop, and the public repo doubles as **build-in-public proof** for judges. Maps exactly onto the wake→cycle→sleep model.

```
GitHub servers, on a schedule (e.g. every 15 min):
   1. spin up a fresh runner
   2. checkout code, install deps
   3. run one wake cycle (agent_cycle.py)
   4. commit updated thesis log back to the repo
   5. runner destroyed
   ...repeats automatically all week, laptop off
```

**US market hours (options-relevant):**
- **Regular session: 9:30 AM – 4:00 PM ET, Mon–Fri** (closed US holidays). **Options only trade in this window** — no pre/after-hours for options (that's stocks only).

| | Regular session |
|---|---|
| **ET** | 9:30 AM – 4:00 PM |
| **UTC** (cron) | **13:30–20:00** (EDT/summer) · 14:30–21:00 (EST/winter) |
| **IST** (local) | **7:00 PM – 1:30 AM** (summer) · 8:00 PM – 2:30 AM (winter) |

⚠️ **DST gotcha:** US clocks shift in Mar & Nov, moving the UTC window ±1 hr. Fix: widen the cron window (e.g. `13-21`) *and* rely on the market-clock guard as the real gatekeeper.

Concrete pieces:
- **Schedule** in `.github/workflows/trade.yml`: `cron: "*/15 13-21 * * 1-5"` (every 15 min, covers both DST windows, weekdays). **GitHub cron is UTC** — independent of laptop clock.
- **Market-clock guard** — first thing each run: call Alpaca's market-clock endpoint; if closed (wrong minute / holiday / weekend), exit immediately → harmless no-op. Handles holidays for free.
- **Secrets** (Alpaca + Gemini keys) → repo Settings → Secrets, never in code.
- **State between runs** — each run is a fresh empty machine, so:
  - Positions → read fresh from **Alpaca account** each run (authoritative).
  - Thesis log → **persist each run** (small JSON/SQLite). Persists *and* becomes a visible audit trail for judges.
    - ⚠️ **Commit-noise:** ~10–15 runs/day committing to `main` would bury real code changes in the history. **Decision — keep logs off `main`:** push log updates to a dedicated **`bot-logs` branch**, *or* use **GitHub Actions Artifacts**, *or* write to a small **DB**. (Cadence is only ~10–15 checks/day and each run takes 5–10 min to load, so timing slack is a non-issue.)

⚠️ **FLAG — GitHub Actions cron is not punctual.** On the free tier, scheduled runs fire on a *best-effort* basis: under load a `*/15` job can slip **10–25 min late**, occasionally skip a slot, or (rarely) not fire at all. **This is fine for us and the design must not assume on-the-minute wakes:**
- The agent is **stateless + rehydrates every wake** (§ "wake cycle"), so a late run just reads *current* market data and decides — it never depends on "which exact slot am I in."
- Never compute anything from wall-clock slot arithmetic (e.g. "it's been exactly 15 min since last run"). Derive everything from live account state + the market-clock guard.
- Each wake already takes ~5–10 min to load/run, and we only need ~10–15 checks/day — so a few minutes' jitter is noise, not a bug.
- **If punctuality ever matters** (it shouldn't here): fall back to Style B (always-on VM) or an external scheduler. Not needed for this project.

Other caveats (all minor): min interval 5 min; workflow must be on the **default branch** to fire.

**Alternative (Style B, spare-time upgrade):** free always-on VM (Oracle Cloud Always-Free / Google Cloud e2-micro) running the continuous loop or a persistent Alpaca CLI session. Real disk → local state "just works," feels more like a live bot, but more setup (SSH, `systemd`/`tmux` to keep it alive).

> **Design consequence:** this commits us to the **cron/CLI headless style** — each wake is a short, self-contained script run, not a long-lived MCP session. Simpler to build.

### MCP vs CLI for this mode
- **MCP server** → the rich interactive brain (many tool calls, reasoning-heavy runs).
- **Alpaca CLI** → lighter for the scheduled headless heartbeat ("cron jobs where MCP is heavier than needed"). Polish decision — either works.

> Mental model: **MCP = hands (idle until called). Agent = brain (wakes on schedule, decides, sleeps). Scheduler = heartbeat spanning the 5–7 days. Alpaca account = memory of what you hold.**

---

## 8. The 3 "wow" features that win the demo

1. **Conviction scorecard** — transparent 0–100 from weighted signals; trades only above threshold. Looks disciplined, not lucky.
2. **Self-grading thesis loop** — agent logs *why* it entered, then later reviews whether the thesis played out ("right on direction, wrong on timing"). Rare; screams "real agent."
3. **Bull-vs-bear debate** — a bull agent and bear agent argue the trade; a judge agent decides. Kills one-shot hallucination; plays to multi-agent/LangChain strengths.

---

## 9. Judging criteria & the P&L demo strategy

**Judging criteria — 5 categories (no published weights):**
1. **P&L Performance** — actual trading P&L in the paper account. *Submission requires the Alpaca account ID so judges verify your P&L.* → P&L genuinely counts.
2. **Technology Implementation** — how well the project uses Trading API + MCP/CLI.
3. **Creativity & Originality** — concept, strategy, agent behavior.
4. **Presentation & Execution** — clarity of the demo + the reasoning shown.
5. **Social engagement** — build-in-public posts (quality + likes/comments/shares).

**Reframe:** P&L is real but it's **1 of 5**. Don't chase the P&L leaderboard (luck over a short window) — aim for **respectable/positive P&L + win the other four** (which are in our control).

**⏰ Timing reality:** live judged window = **Aug 28 – Sep 4 = ~5–6 trading days**, measured on the **fresh account** (can't pre-run). All live P&L comes from one clean 5-day window. → Dial everything in on a **dev/throwaway account during Aug 18–28**; run the fresh account clean from Aug 28.

**The problem:** naked long options are **low win-rate** (lose small often, win big rarely) — a bad profile for 5 days. Tilt toward a smoother curve:
- **Higher-delta contracts (~0.60–0.70, near/in-the-money)** instead of cheap OTM lottery tickets → higher win rate, less theta.
- **Take profits early (+25–40%)** → bank *realized* gains inside the window (realized green > unrealized).
- **Cut losers fast**; treat **cash as a position** — in a risk-off week, stay mostly flat. A flat account beats a bleeding one, and "the agent knew not to trade" is a strong talking point.
- **Don't swing for the fences** — modest consistent green + great process beats a gamble that may crater.

**The hedge — backtest for the video:** 5 live days is noise. Show a **backtest of the signal engine over months of historical stock data** to prove the edge regardless of the live week.
- ⚠️ **Data caveat (verified):** Alpaca option greeks/IV are **snapshot/live-only — no history.** Can't cleanly backtest *options* P&L historically. → Backtest the **directional signal on historical stock bars** (free/easy); approximate option outcomes.
- ✅ **Verified good:** greeks (delta/gamma/theta/vega/rho) + IV are **free on paper**, options enabled by default → the *live* engine has all it needs.

**Presentation (1 of 5, 100% in our control):** equity curve (live + backtest), 2–3 **hero trades** with full agent reasoning, **risk-gate-in-action**, **self-grading loop**, metrics dashboard (win rate, avg win/loss, max drawdown).

---

## 10. Setup checklist (all free)

- [ ] **Hugging Face token** — huggingface.co → Settings → Access Tokens (paid Inference Providers, funded by Yugo's ~$100). Pick model from [HF supported-models list](https://huggingface.co/inference/models).
- [ ] **Gemini API key** — aistudio.google.com → "Get API key" (no billing) — free fallback
- [ ] **Alpaca paper account** — alpaca.markets → sign up → generate paper keys
- [ ] **Enable options trading** on the paper account (Level 1–3; Level 3 = spreads). Request early — approval can lag.
- [ ] **Clone + run Alpaca MCP server** locally with paper keys
- [ ] `.env` with all keys (so swapping accounts later = one edit)

### Base URLs
- Paper trading: `https://paper-api.alpaca.markets`
- Market data: `https://data.alpaca.markets`

### Package note
Use **`alpaca-py`** (current SDK). Ignore `alpaca-trade-api` — it's deprecated.

---

## 11. Submission rules & deliverables (don't get disqualified)

**Required submission deliverables:** project title + short/long description, technology & category tags, cover image, **video presentation**, **slide presentation**, **public GitHub repo**, demo app platform + URL, **Alpaca paper account ID** (for P&L judging), up to **5 social post links**.

- **Dev:** use any paper account during development.
- **Submission (REQUIRED):** create a **brand-new, dedicated Alpaca paper account** for the final submission. Reused/existing accounts are **not eligible for judging**. → just swap keys in `.env` at the end.
- **Build in Public (extra challenge, free points):** post progress on **X** and **LinkedIn**, tag **@lablabai / @AlpacaHQ** (LinkedIn: lablab.ai, Alpaca). Submit up to **5 post links** with final submission.
  - Milestone posts: day-1 architecture → MCP wired up → first agent-placed trade → risk gate in action → final demo.
  - Claude can help draft posts; user posts them (no auto-posting).

---

## 12. Build milestones

1. **Setup** — keys, options enabled, MCP server running locally.
2. **Wire the brain** — Gemini LangChain/LangGraph agent loads MCP tools via `langchain-mcp-adapters`.
3. **Risk gate** — `propose_trade` tool sits between LLM and MCP execute; enforce sizing/limits.
4. **Decision engine** — implement conviction scorecard (Tier 1 + chosen Tier 2 metrics).
5. **Thesis loop** — analyze → explain → risk-check → execute → log reasoning.
6. **Self-grading** — post-trade review of logged theses.
7. **(Stretch) bull/bear debate.**
8. **Scheduled mode** — Alpaca CLI cron runtime.
9. **Demo polish + fresh account swap + build-in-public posts.**

---

## 13. Open questions / to verify

- [x] **Judging criteria** — RESOLVED. 5 categories: P&L, Tech Implementation, Creativity/Originality, Presentation, Social. P&L is judged via submitted account ID. See §9.
- [x] **Options data on free tier** — RESOLVED. Greeks (delta/gamma/theta/vega/rho) + IV available free on paper via option **snapshot** (live-only, no history). Options enabled by default. See §9.
- [x] **Project folder** — CONFIRMED. Code + doc live in `C:\Users\chira\Desktop\alpaca-trading-agent\`, git repo pushed to `github.com/chiragshah2357/Alpaca-Trading-Hackathon`.
- [ ] **HF model pick** — Chirag skimming [HF Inference Providers](https://huggingface.co/inference/models); shortlist **Kimi-K3 / DeepSeek-V4-Pro**. Decide which one (or which per-teammate mix for the bake-off) before build. **Cost is settled — see §13a below (spoiler: a non-issue).**
- [ ] **Backtest scope** — decide how far to approximate options P&L historically given snapshot-only greeks (direction backtest on stock bars is the fallback).
- [ ] **Watchlist** — finalize the ~20–40 liquid optionable names before Aug 28.

### 13a. Model cost & free credits (RESOLVED — cost is not a constraint)

**Per-token cost** (USD per 1M tokens on HF Inference Providers; ballpark — varies by which provider HF routes to):

| Model | Input | Output | Context | Notes |
|-------|-------|--------|---------|-------|
| **DeepSeek V4 Pro** | ~$1.74 | ~$3.48 | large | Blended ~$2.17/M; some routes (OpenRouter) as low as ~$0.44 / ~$0.87 |
| **DeepSeek V4 Flash** | ~$0.14 | ~$0.28 | 1M | Cheapest capable option — good for high-frequency steps |
| **Kimi K2.6 / K3** | ~$0.95 | ~$4.00 | 256K | Long context; output is the pricey part |
| **Qwen (7B class)** | ~$0.30 | ~$0.80 | 131K | Max / 235B-class costs more (not pinned exactly) |
| **Llama 3.3 70B** | ~free | ~free | — | Already **free on Groq** — keep for cheap sentiment step |

**The only number that matters:** our §6 budget is **~300k tokens/week**. Even on the priciest option (DeepSeek V4 Pro, ~$2.17/M blended) that's **~$0.65/week** → **~$2–5 total** across dev + the judged window, maybe **$15–20** if we 5× usage with debate loops across three test accounts. **Yugo's ~$100 is far more than enough — pick the best model, not the cheapest.**

**Free-credit paths on HF** (for reference — we don't really need them given the above):
- **Free tier:** ~$0.10/mo (~100K) Inference Provider credits — trial trickle only.
- **PRO ($9/mo):** $2/mo credits + **2M monthly Inference Provider credits** + 25 min/day H200 ZeroGPU. The 2M allowance is the real perk.
- **Startup perk:** some partner programs offer **6 months PRO free** for eligible startups — worth a look only if one of us qualifies.
- **Keep the free levers we already have:** Gemini free tier (fallback brain) + Groq free tier (Llama for cheap sentiment) preserve the $100 almost entirely.

> **Decision:** put the paid HF token on a **strong model (DeepSeek V4 Pro or Kimi K3)** for the thesis; route cheap high-frequency work to **Groq/Gemini free tiers**. Expected spend: a few dollars of the $100. Cost is closed as a concern.
>
> *Figures gathered Aug 2026 from pricepertoken, morphllm, DeepInfra, and Hugging Face pricing pages — re-verify live before committing to a provider.*

---

## 14. Locked decisions (summary)

> **Track 1 (Options Alpha) · paid HF Inference Provider brain (Kimi-K3 / DeepSeek-V4-Pro TBD, Gemini/Groq free fallback) funded by Yugo's ~$100 · Hybrid decision (LLM thesis + rule-based execution) · built on Alpaca MCP server via langchain-mcp-adapters · risk gate between brain and orders · multi-signal conviction engine with options-aware metrics · deterministic funnel keeps LLM tokens at the last mile · P&L-tuned for the 5-day judged window (higher-delta, take profits early, cash-is-a-position) + historical backtest for the video · self-grading thesis log · scheduled via GitHub Actions cron (headless, laptop-off) with market-clock guard + log kept off `main` (bot-logs branch / Artifacts / DB) · fresh paper account at submission · build-in-public posts throughout.**

### 14a. Pre-event bake-off (Aug 18–28)

Provider swap is one `.env` edit, so we exploit the week before kickoff: **all three of us run the agent on our own paper accounts**, each tuned a bit differently — e.g. one **conservative** (higher conviction floor, lower deployment), one **more volatile/aggressive**, one middle. Three parallel dev sessions ≈ 3× the live-testing data. Come Aug 28 we **pick the best-performing config** and run it on the fresh submission account.

- Optional **"demo-mode" safety valve** (Alok's idea): if the agent hasn't placed a single trade by ~Day 3 of the *judged* window, temporarily relax `MIN_CONVICTION` (e.g. 65 → 55) so judges have at least one or two small, safe live trades to grade. Keep it a deliberate, logged override — not the default.

---

### Judging criteria → where we score (§9)
| Criterion | Our play |
|-----------|----------|
| P&L Performance | Higher-delta + early profits + cash discipline over the 5-day window; don't gamble |
| Technology Implementation | MCP server + CLI, the "core of the theme" |
| Creativity & Originality | Multi-tier conviction engine, bull/bear debate, self-grading |
| Presentation & Execution | Equity curve + hero trades + risk-gate-in-action + metrics dashboard |
| Social engagement | Build-in-public posts at each milestone, tagging @lablabai / @AlpacaHQ |
