# Harness integration — coexistence of the two branches

This branch merges Yugo's DSH decision layer (PR #4) with our runtime so **both live on
one tree with no conflicts**. 72 tests pass (our 67 + his 5).

## What changed to make them coexist

- **`agent/` namespace → Yugo's.** Our model layer moved `agent/` → **`model/`**
  (`model/config.py`, `model/llm.py`). His `agent/` decision package now owns that dir.
- **Harness: LangGraph dropped.** Our loop is a plain Python runner (`harness/run.py`);
  removed `harness/graph.py`, `harness/state.py`, the `use_langgraph` path, and the
  `langgraph` dependency — honoring his design non-goal.
- **`.gitignore`** unified to the union of both branches.

## One pick per category (canonical owner)

| Category | Canonical | Notes / redundant piece to retire later |
|---|---|---|
| Risk engine | `risk_engine/` (shared) | — |
| Decision **input** | **Yugo** — `agent/candidates.py` (N bounded candidates) | our single-plan `strategy_api` stays only to feed the current UI |
| Decision **safety** | **Yugo** — candidates hide exact sizes from the model | — |
| Gate / limits | **Yugo** — `agent/gate.py` + `agent/limits.py` | our `risk_engine/limits.py` + `validate_plan` stay until the loop uses the candidate flow |
| **Runtime** | **Ours** — `harness/` loop + `run_agent`/`loop.py` + cron + Docker | his single local slice |
| MCP **read** | **Yugo** — `agent/dsh` read-only snapshot (verified) | our `feed/AlpacaDataSource` REST kept as fallback |
| MCP **write** | **Ours** — `harness/mcp_executor.py` | — |
| Ledger | **Ours** — `ledger.py` (trade log + self-grading) | fold his `agent/ledger.py` decision-idempotency into it |
| UI / backtest / grading | **Ours** — `webui/`, `backtest/`, `grade.py` | — |

## Two decisions still open for you + Yugo

1. **Default decider:** the **DSH agent** (`agent/dsh`) or the **LLM decider**
   (`harness/llm.py` + `model/`)? Both are present and satisfy the same "choose one
   action + reason" idea; pick the default for the judged run.
2. **Default approval mode:** **human-in-the-loop** (Yugo's gate default) or
   **autonomous** (our loop default)?

## Follow-up consolidation (not done here — would touch the loop, kept out to avoid breakage)

- Rewire `run_cycle` to drive **candidates → chosen id → `agent.gate`** instead of the
  single-plan `validate_plan`, then retire our `validate_plan`/duplicate limits.
- Merge `agent/ledger.py` idempotency into `ledger.py`; keep one ledger.
- Point OBSERVE at the DSH read-only MCP snapshot via the `DataSource` protocol.
