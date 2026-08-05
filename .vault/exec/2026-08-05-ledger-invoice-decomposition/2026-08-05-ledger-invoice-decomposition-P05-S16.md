---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9691b3aa2c7a95aee41296a31dd8d3c606d2d68e65ef20450cd0f44589b1a004'
step_id: 'S16'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Ground the chain on an exempt-services example proving the under-declaration direction is closed

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Add `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_exempt.py` driving one IVA-exempt professional service through the same three chain links as the rated sibling.
- Ground the figures the same way: the invoice's own base imponible for casilla 01, and the RIRPF art. 95.1 rate from the registry parameter catalogue for the retencion.
- Assert the declared category is what makes the cuota zero, reading the Axis-A table rather than testing for a null field, since that distinction is what the whole recovery rests on.
- Pin the substrate-absent branch's shortfall to the withheld amount rather than to a literal, tying the two losses to one another.
- Assert the cash falls strictly below the base, fixing the case's identity as the under-declaring direction.
- Omit the rate-inversion guard the rated sibling carries, and record in the module why it cannot discriminate here.

## Outcome

Landed as commit `e038988344` (1 file, +294, 0 deletions).

Raw counts, serial runs (`-n 0`): the module alone 7 passed, 0 failed, 0 skipped; with its rated sibling 14 passed, 0 failed, 0 skipped.

The under-declaration direction is closed by visibility rather than by exclusion, and the module pins exactly that. An exempt operation has no cuota to offset the withholding, so the bank credit of 850 sits strictly below the 1000 ingresos integros. Without its base, casilla 01 receives the 850 and the return under-declares by precisely the 150 withheld, while the offsetting retenciones credit is lost at the same time. The fallback is deliberately kept, because dropping the row would under-declare by the whole 850 instead of by 150, so the ungrounded screen firing IS the closure.

The exempt case earns separate coverage rather than a parameter on the rated one, and the mutation proof below is the evidence: restoring the pre-relaxation precondition reddens two gates here and none in the rated module.

## Notes

The rate-inversion guard was written, run, and removed, and the removal is the finding. With no cuota the invoice total equals the base, so cash equals base times one minus the rate exactly, and inverting the rate off the cash returns the same 150 by coincidence. The assertion therefore excluded nothing while looking like a check. It is recorded in the module docstring as deliberately absent rather than silently dropped, because a later reader comparing the two siblings would otherwise read the asymmetry as an oversight. The cuota is what breaks the coincidence, which is why that guard belongs to the rated case only.

The substrate-absent variant drops the declared category along with the base, which is not incidental. A base with no cuota and a bank credit with nothing recorded against it are indistinguishable on the amounts alone; only the declared category separates exempt income from untagged income. Keeping the category while dropping the base would have described a different, narrower row than the clean-bank-import state the branch is meant to represent.

### Mutation proofs

Run in process by rebinding the function under test, so no broken state existed in the working tree at any point.

- Restore the pre-relaxation withheld precondition, where the cuota is determinable only from a recorded `iva_amount`: 2 of 7 gates red here, 0 of 7 red in the rated module. That asymmetry is the whole justification for the separate module.
- Sum the gross amount unconditionally: 3 of 7 red.
- Sum only the declared base: 2 of 7 red.
- Apply the retencion rate to an IVA-inclusive total: 2 of 7 red.
