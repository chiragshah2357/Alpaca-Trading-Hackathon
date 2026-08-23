import { promisify } from 'node:util'
import { execFile } from 'node:child_process'
import Schema from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'

const execFileAsync = promisify(execFile)

export const name = 'portfolio-tools'
export const inject = ['tools']

export const Config = Schema.object({
  repositoryRoot: Schema.string().required(),
  scenario: Schema.string().required(),
  ledgerPath: Schema.string().required(),
  pythonExecutable: Schema.string().default('python3'),
})

const CONTEXT_OUTPUT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    context_id: { type: 'string', required: true },
    scenario_id: { type: 'string', required: true },
    risk: { type: 'json', required: true },
    candidates: { type: 'json', required: true },
    decision_contract: { type: 'json', required: true },
  },
}

const SUBMIT_OUTPUT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    decision_id: { type: 'string', required: true },
    scenario_id: { type: 'string', required: true },
    decision: { type: 'json', required: true },
    gate: { type: 'json', required: true },
  },
}

async function bridge(config, args) {
  try {
    const { stdout } = await execFileAsync(config.pythonExecutable, ['-m', 'agent.cli', ...args], {
      cwd: config.repositoryRoot,
      encoding: 'utf8',
      maxBuffer: 1024 * 1024,
    })
    return JSON.parse(stdout)
  } catch (error) {
    if (error?.stdout) {
      try {
        return JSON.parse(error.stdout)
      } catch {
        // Fall through to a concise infrastructure error.
      }
    }
    const detail = error?.stderr?.trim() || error?.message || String(error)
    throw new Error(`deterministic bridge failed: ${detail}`)
  }
}

function rendered(value) {
  return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
}

export function apply(ctx, config) {
  ctx.tools.register(defineTool({
    name: 'get_decision_context',
    description: 'Read the authoritative risk snapshot and complete set of admissible portfolio candidates. Call this before selecting anything.',
    parameters: {},
    output: {
      schema: CONTEXT_OUTPUT,
      render: (_args, value) => rendered(value),
    },
    execute() {
      return bridge(config, ['context', '--scenario', config.scenario])
    },
  }))

  ctx.tools.register(defineTool({
    name: 'submit_decision',
    description: 'Select exactly one candidate returned by get_decision_context. The deterministic gate validates it and creates paper-only dry-run orders.',
    parameters: {
      context_id: { type: 'string', required: true },
      candidate_id: { type: 'string', required: true },
      reason: { type: 'string', required: true },
      decision_id: { type: 'string', required: true },
    },
    output: {
      schema: SUBMIT_OUTPUT,
      render: (_args, value) => rendered(value),
    },
    async execute(args, exec) {
      const value = await bridge(config, [
        'submit',
        '--scenario', config.scenario,
        '--context-id', args.context_id,
        '--candidate-id', args.candidate_id,
        '--reason', args.reason,
        '--decision-id', args.decision_id,
        '--ledger', config.ledgerPath,
      ])
      if (value.gate?.status === 'approved_for_dry_run') exec.concludeTurn()
      return value
    },
  }))
}
