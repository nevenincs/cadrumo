---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:531da3c48c25e95b0da5168aa30b52086ff39a049a2d5891880b75872509a92e'
step_id: 'S31'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Read the statutory retencion rate from the registry general_rate at every oracle expectation site, reserving the bound accessor for assertions genuinely about the inference cap

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Change the two oracle modules (`test_ledger_income_chain_oracle_rated.py`, `test_ledger_income_chain_oracle_exempt.py`) to read the RIRPF art. 95.1 general rate through the registry's statutory `general_rate` accessor at all six sites where the docstrings already claimed to anchor on it, replacing reads of the inference cap accessor.
- Leave the cap accessor in place only for the assertions genuinely about the upper bound the withheld inference refuses to exceed -- a different claim that today merely coincides in value with the statutory rate.
- Leave the IVA rate as a literal on purpose: 21% is the fixture's own choice of tier, so the registry is consulted for what 21% IS, not for which tier this invoice used.

## Outcome

Landed as commit `0e4ead7c7c`, "test(registry): let the oracle expectations read the rate their docstrings claim".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

The defect the commit closes: both oracle modules' docstrings said their expectation was anchored on the statutory general rate, but the assertion code read the inference cap instead. The cap returns the same number today, so the tests passed while the prose overstated what was actually verified -- an expectation asserted through the cap is right for the wrong reason and stops being right at all the moment the two are deliberately set apart. Mutation-proved per the commit message: offsetting the statutory expectation by one reddens the rated module.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_rated.py src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_exempt.py -n 0 -q
```

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches before the namespace error was caught.
