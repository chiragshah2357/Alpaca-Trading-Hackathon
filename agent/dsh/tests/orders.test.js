import assert from 'node:assert/strict'
import test from 'node:test'

import { occSymbol, resolveHedgeContract, buildPlaceArgs, placeGateOrders } from '../alpaca-orders.js'

const NOW = new Date(Date.UTC(2024, 8, 6)) // 2024-09-06

test('occSymbol builds a valid OCC option symbol', () => {
  assert.equal(occSymbol('SPY', new Date(Date.UTC(2024, 8, 20)), 'P', 520), 'SPY240920P00520000')
})

test('resolveHedgeContract picks nearest expiry then nearest strike', () => {
  const chain = {
    SPY240913P00520000: {},
    SPY240920P00520000: {}, // 14 days out — the target
    SPY240920P00500000: {},
    SPY240920C00520000: {}, // a call, must be ignored
  }
  const order = { symbol: 'SPY', strike: 519, expiry_days: 14, contracts: 3, intent: 'buy_to_open', structure: 'protective_put' }
  const resolved = resolveHedgeContract(order, chain, NOW)
  assert.equal(resolved.symbol, 'SPY240920P00520000')
})

test('resolveHedgeContract throws when nothing resolves', () => {
  assert.throws(() => resolveHedgeContract(
    { symbol: 'SPY', strike: 500, expiry_days: 14 }, {}, NOW,
  ), /no listed put resolves/)
})

test('buildPlaceArgs maps to the confirmed place_option_order schema', () => {
  const args = buildPlaceArgs(
    { symbol: 'SPY240920P00520000' },
    { intent: 'buy_to_open', contracts: 3, client_order_id: 'dry-abc123' },
  )
  assert.equal(args.symbol, 'SPY240920P00520000')
  assert.equal(args.side, 'buy')
  assert.equal(args.qty, '3') // string, per the server schema
  assert.equal(args.type, 'market')
  assert.equal(args.time_in_force, 'day')
  assert.equal(args.position_intent, 'buy_to_open')
  assert.equal(args.client_order_id, 'dry-abc123')
})

test('buildPlaceArgs omits client_order_id when absent', () => {
  const args = buildPlaceArgs({ symbol: 'SPY240920P00520000' }, { intent: 'sell_to_close', contracts: 2 })
  assert.equal(args.side, 'sell')
  assert.equal(args.qty, '2')
  assert.equal(args.position_intent, 'sell_to_close')
  assert.equal(args.client_order_id, undefined)
})

test('placeGateOrders skips non-placeable structures and places the hedge', async () => {
  const calls = []
  const client = { async callTool(req) { calls.push(req); return { structuredContent: { ok: true } } } }
  const chain = { SPY991220P00520000: {} } // far-future expiry so it resolves against the real clock
  const io = { stderr: { write() {} } }
  const results = await placeGateOrders(client, [
    { structure: 'iron_condor', symbol: 'SPY', contracts: 1 },
    { structure: 'protective_put', symbol: 'SPY', strike: 520, expiry_days: 14, contracts: 2, intent: 'buy_to_open' },
  ], chain, io)
  assert.equal(results[0].status, 'skipped')
  assert.equal(results[1].status, 'placed')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].name, 'place_option_order')
})
