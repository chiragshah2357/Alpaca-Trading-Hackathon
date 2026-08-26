import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import { ALPACA_MCP_VERSION, decodeMcpResult } from './alpaca-readonly.js'

// Order-capable connection to the SAME official server, still paper-enforced. Kept
// separate from the read-only wrapper so the write surface is opt-in and auditable.
const ORDER_TOOLSET = 'account,trading,options-data'
const PLACE_TOOL = 'place_option_order'

// Structures we can resolve to a concrete listed contract today. Multi-leg income
// (iron_condor / spreads) needs multi-leg order support + per-leg OCC resolution and is
// intentionally NOT auto-placed yet — the loop logs it as skipped rather than mis-trade.
const PLACEABLE_STRUCTURES = new Set(['protective_put'])

function orderChildEnv(env) {
  const key = env.ALPACA_API_KEY
  const secret = env.ALPACA_SECRET_KEY
  if (!key || !secret) throw new Error('Alpaca paper credentials are not configured for order placement')
  return Object.fromEntries(Object.entries({
    PATH: env.PATH,
    HOME: env.HOME,
    LANG: env.LANG,
    UV_CACHE_DIR: env.UV_CACHE_DIR,
    UV_NO_PROGRESS: '1',
    ALPACA_API_KEY: key,
    ALPACA_SECRET_KEY: secret,
    ALPACA_PAPER_TRADE: 'true', // hard paper enforcement — never live from this path
    ALPACA_TOOLSETS: ORDER_TOOLSET,
  }).filter(([, value]) => value !== undefined))
}

export async function connectAlpacaOrders(env = process.env) {
  const transport = new StdioClientTransport({
    command: 'uvx',
    args: [`--from=alpaca-mcp-server==${ALPACA_MCP_VERSION}`, 'alpaca-mcp-server'],
    env: orderChildEnv(env),
    stderr: 'pipe',
  })
  const client = new Client({ name: 'alpaca-portfolio-orders', version: '0.1.0' })
  await client.connect(transport)
  return { client, close: () => client.close() }
}

function pad(n, width) {
  return String(n).padStart(width, '0')
}

// Build an OCC symbol: ROOT + YYMMDD + C/P + strike*1000 (8 digits). e.g. SPY240920P00520000
export function occSymbol(root, expiry, right, strike) {
  const yy = pad(expiry.getUTCFullYear() % 100, 2)
  const mm = pad(expiry.getUTCMonth() + 1, 2)
  const dd = pad(expiry.getUTCDate(), 2)
  const strk = pad(Math.round(strike * 1000), 8)
  return `${root.toUpperCase()}${yy}${mm}${dd}${right.toUpperCase()}${strk}`
}

function parseOccExpiry(occ) {
  const ymd = occ.slice(-15, -9)
  return new Date(Date.UTC(2000 + Number(ymd.slice(0, 2)), Number(ymd.slice(2, 4)) - 1, Number(ymd.slice(4, 6))))
}

// Resolve a hedge order (underlying + strike + expiry_days) to a real listed contract by
// scanning the readonly option-chain snapshot for the nearest expiry, then nearest strike.
// Returns { symbol, strike, expiry } or throws — we never place an unresolved contract.
export function resolveHedgeContract(order, optionChain, now = new Date()) {
  const targetDays = order.expiry_days
  const targetStrike = order.strike
  const entries = Object.keys(optionChain || {})
  let best = null
  for (const occ of entries) {
    if (occ.length < 15) continue
    if (occ[occ.length - 9] !== 'P') continue
    let expiry
    try { expiry = parseOccExpiry(occ) } catch { continue }
    const days = Math.round((expiry - now) / 86_400_000)
    if (days <= 0) continue
    const strike = Number(occ.slice(-8)) / 1000
    const score = [Math.abs(days - targetDays), Math.abs(strike - targetStrike)]
    if (best === null || score[0] < best.score[0] || (score[0] === best.score[0] && score[1] < best.score[1])) {
      best = { symbol: occ, strike, expiry, score }
    }
  }
  if (best === null) throw new Error(`no listed put resolves ${order.symbol} ~${targetStrike} @ ${targetDays}d`)
  return { symbol: best.symbol, strike: best.strike, expiry: best.expiry }
}

function sideFor(intent) {
  if (intent === 'buy_to_open' || intent === 'buy_to_close') return 'buy'
  if (intent === 'sell_to_open' || intent === 'sell_to_close') return 'sell'
  throw new Error(`unknown order intent: ${intent}`)
}

// Confirmed against alpaca-mcp-server 2.2.1 (place_option_order): single-leg orders
// take qty (string), type, time_in_force, symbol, side, plus optional position_intent
// and client_order_id (idempotency). The gate's intent maps directly to position_intent;
// the gate's client_order_id is passed through so a timed-out submit can be retried safely.
export function buildPlaceArgs(resolved, order) {
  const args = {
    symbol: resolved.symbol,
    side: sideFor(order.intent),
    qty: String(order.contracts),
    type: 'market',
    time_in_force: 'day',
    position_intent: order.intent,
  }
  if (order.client_order_id) args.client_order_id = order.client_order_id
  return args
}

export async function placeGateOrders(client, gateOrders, optionChain, io = { stderr: process.stderr }) {
  const results = []
  for (const order of gateOrders) {
    if (!PLACEABLE_STRUCTURES.has(order.structure)) {
      results.push({ order, status: 'skipped', reason: `structure ${order.structure} not auto-placeable yet` })
      io.stderr.write(`orders: skipped ${order.structure} (multi-leg placement pending)\n`)
      continue
    }
    try {
      const resolved = resolveHedgeContract(order, optionChain)
      const args = buildPlaceArgs(resolved, order)
      const raw = await client.callTool({ name: PLACE_TOOL, arguments: args })
      results.push({ order, status: 'placed', contract: resolved.symbol, result: decodeMcpResult(raw) })
      io.stderr.write(`orders: placed ${args.side} ${args.qty}x ${resolved.symbol}\n`)
    } catch (error) {
      results.push({ order, status: 'failed', reason: error instanceof Error ? error.message : String(error) })
      io.stderr.write(`orders: FAILED to place ${order.structure}: ${error}\n`)
    }
  }
  return results
}
