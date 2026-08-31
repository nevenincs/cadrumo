---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f98418cc694c1a1210467729f20b0d8e13ef30fa245fe704f76f8a6791797525'
step_id: 'S183'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in bindings.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S183.md`

## Notes

- The public `bindings.py` surface was reduced below the unchanged 1,250-line module policy by moving cohesive binding-family logic to defining sibling modules. The independent source review observed a live 894-line primary; the prior executor observed 1,032 lines during the same shared-tree work. Both are below policy, and every extracted helper is at most 179 lines under the unchanged 180-line callable policy. No baseline or threshold change belongs to this Step.
- The supplied focused receipt is executor-reported only: `48 passed in 51.93s`. Its literal command was not retained, so this record deliberately does not invent a `verify:` command.
- Independently reviewed targeted Ruff/check, import, and compile probes were clean. The non-mutating full size audit stalled and yielded no result; this record makes no global size-audit pass claim.
- `src/cadrumo/application/modelo/_calculation_actions.py` carries concurrent relocation work. The source commit stages the reviewed bindings extraction with an isolated index and excludes that peer relocation.
