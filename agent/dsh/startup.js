import { resolve } from 'node:path'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Command } from 'commander'
import { parseCmdline } from '@deepseek-ai/dsh-cmdline'

export const name = 'portfolio-startup'
export const inject = ['cmdlineArgs']

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')

function command() {
  return new Command()
    .name('dsh --profile portfolio-agent')
    .description('Run one bounded regime-adaptive portfolio decision.')
    .helpOption('-h, --help', 'show this help')
    .requiredOption('--scenario <name>', 'fixed scenario: calm, elevated, or stressed')
    .option('--ledger <path>', 'dry-run JSONL ledger', '.agent/decisions.jsonl')
    .argument('[instruction...]', 'decision objective')
}

export function apply(ctx) {
  const program = command()
  program.action((instructionParts, options) => {
    const instruction = instructionParts.join(' ').trim()
    if (instruction === '') program.error('error: an instruction is required')
    if (!['calm', 'elevated', 'stressed'].includes(options.scenario)) {
      program.error('error: scenario must be calm, elevated, or stressed')
    }
    ctx.provide('portfolioStartup', {
      repositoryRoot,
      scenario: options.scenario,
      ledgerPath: resolve(options.ledger),
      instruction,
    })
  })
  parseCmdline(ctx, program)
}
