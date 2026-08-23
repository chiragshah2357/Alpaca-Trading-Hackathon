import assert from 'node:assert/strict'
import test from 'node:test'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const repositoryRoot = resolve(import.meta.dirname, '../../..')

test('python bridge exposes the expected fixed candidate sets', () => {
  const expected = {
    calm: ['hold'],
    elevated: ['hold', 'harvest_income'],
    stressed: ['partial_hedge', 'full_hedge'],
  }
  for (const [scenario, ids] of Object.entries(expected)) {
    const stdout = execFileSync('python3', ['-m', 'agent.cli', 'context', '--scenario', scenario], {
      cwd: repositoryRoot,
      encoding: 'utf8',
    })
    const value = JSON.parse(stdout)
    assert.deepEqual(value.candidates.map(candidate => candidate.candidate_id), ids)
  }
})
