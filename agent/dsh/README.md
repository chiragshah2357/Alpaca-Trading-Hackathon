# DSH local harness

This bundle connects the existing deterministic risk engine to a single DSH agent.
The model can access exactly three tools:

- `get_decision_context`: retrieves the risk snapshot and the admissible candidates.
- `submit_decision`: selects one candidate, validates it through the deterministic
  gate, and records a paper dry run.
- `get_alpaca_readonly_snapshot`: reads the paper account, positions, and SPY market
  data through the official Alpaca MCP server. Order, cancellation, and account
  mutation tools are not exposed.

The model cannot invent symbols, orders, quantities, or risk values. A successful
`submit_decision` result still has `human_approval_required: true` and is never sent
to Alpaca.

## Setup

Use Node.js 22 or later. DSH is a developer preview, so the `package-lock.json`
pins the `0.1.1-rc.2` dependency line.

```bash
cd agent/dsh
npm ci
DSH_HOME="$PWD/../../.dsh" ./node_modules/.bin/dsh \
  plugin --profile portfolio-agent add "$PWD"
```

## Keyless verification

The verification suite runs the calm, elevated, and stressed scenarios through
the official replay adapter without using an HF token, Alpaca credentials, or a
Modal secret.

```bash
cd agent/dsh
npm test
npm run test:alpaca-schema
npm run test:profile
cd ../..
python3 -m unittest discover -s tests -v
```

`test:profile` creates a temporary `DSH_HOME` and dry-run ledger. It does not
connect to a real account, remote model, or paper-order endpoint.
`test:alpaca-schema` starts the official server with non-secret placeholders and
calls only `tools/list`; it does not invoke an Alpaca API tool.

## Alpaca paper read-only boundary

`get_alpaca_readonly_snapshot` starts `alpaca-mcp-server==2.2.1` as a stdio child
process and calls only this internal allowlist:

- `get_account_info`
- `get_all_positions`
- `get_stock_bars`
- `get_stock_latest_trade`
- `get_option_chain`

Even though the official server also provides order, close-position, cancellation,
exercise, and account-configuration tools, those tools are never registered with
the DSH model.

Credentials are passed only from the DSH process environment to the MCP child via
`ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. They are not written to configuration,
sessions, or the ledger. The connection always sets `ALPACA_PAPER_TRADE=true`; the
free-data feeds are `iex` for stocks and `indicative` for options.

Account IDs, account numbers, user IDs, and related identifiers are removed
recursively before a result reaches the model or session. External strings, arrays,
and the total result size are also bounded.

If credentials are absent, the tool fails closed before connecting to the API.
When credentials become available, run only this read-only tool first and never put
paper-account identifiers or credentials in logs or commits.
