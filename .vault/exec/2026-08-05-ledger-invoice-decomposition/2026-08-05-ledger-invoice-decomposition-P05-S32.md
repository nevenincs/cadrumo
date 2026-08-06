---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:446a8ea8153fcc57b4f6d85a310d7bb7309a6d1eabb127fd7c8e67f9f6ac0b8b'
step_id: 'S32'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Add a sub-cap oracle case on the 7 percent inicio-de-actividad registry rate so the bound is calibrated at more than one point

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Add the second-paragraph RIRPF art. 95.1 case to `test_ledger_income_chain_oracle_rated.py`: the reduced retencion rate for the periodo of inicio de actividades profesionales and the two following periods, on the same invoice, base, and cuota as the existing cases, differing only in the withheld figure and the cash it implies.
- Pin that the two registry rates (general and reduced) genuinely differ, so the new case cannot silently test nothing while still passing.
- Extend the row builder to take an optional cash figure defaulting to the existing value, so every prior case stays byte-unchanged in behaviour.

## Outcome

Landed as commit `3f88b15d06`, "test(registry): calibrate the withheld inference at a rate below its own ceiling".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

The gap the commit closes: every pre-existing case in the module withheld at the general rate, which is also the ceiling the inference refuses to exceed -- calibrated at exactly one point, the bound itself, so a derivation that always returned its maximum would have satisfied all of them. Demonstrated rather than argued per the commit message: clamping the inference to `maximum_supported` fails only the two new sub-cap cases, while the eight pre-existing ones pass unchanged because they sit on the bound.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_rated.py -n 0 -q
```

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches before the namespace error was caught.
