---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2ff41ed8d29cbe3086ffadfa64f8515065a85dbd8070f4c70ebaedfdfcbe1656'
step_id: 'S07'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W02.P03.S07

## Outcome

Implemented the reachability probe on the existing per-family seam, and found that the seam's one prior occupant could not fail.

## The seam

The pattern the Step points at is real and correct: a `NamedTuple` carrying only the attributes the matcher reads, a synthetic observation built from the selector's OWN declared values, run through the **real** matcher the resolver builds — not a reimplementation of the match rule — called from `validate_*_binding_definition` so it runs at registry build.

## What the prior occupant proved

`_renta_gastos_pago_fraccionado_reachability_probe` is structurally incapable of failing. Its matcher tests `observation.target_casilla_id == selector.target_casilla_id` while the probe constructs the observation from that same field, so it asks `x == x`. Driven directly:

    '02'                   : probe PASSED
    '9999'                 : probe PASSED
    'not-a-real-casilla'   : probe PASSED

The governing ADR chose registry-build reachability as the **primary** mechanism for the silent-zero class. Its only implementation reported green for every input, which is worse than no probe: it occupies the place coverage would sit.

## Where a selector-derived probe genuinely bites

Only where the matcher tests membership in a set the selector declares. Surveying all five families' matchers against their selector constraints:

| family | matcher shape | can the probe fail? |
|---|---|---|
| renta income | scalar casilla equality | no |
| renta gastos estimación directa | scalar equality ×3 | no |
| renta gastos pago fraccionado | scalar casilla equality | no |
| OSS | 4 scalars + `transaction_kinds` set, `MinLen(1)` | no |
| **IVA** | 4 set/scalar tests, `cash_accounting_treatments` **unbounded** | **yes** |

`_IvaLedgerSelector.cash_accounting_treatments` is the one set-valued axis in the whole family set carrying no `MinLen`. An empty tuple is constructible today, and the matcher tests `observation.cash_accounting_treatment in set(...)` against it, so it rejects every treatment the enum defines. Verified directly: `[('none', False), ('taxpayer_regime', False), ('supplier_regime', False)]`.

Such a binding compiles clean, validates clean, and resolves to zero for every taxpayer forever — indistinguishable from one who genuinely had no IVA of that kind, and unreachable by any runtime data because the defect *is* the absence of matches. That is precisely the class this Wave exists to catch.

## What landed

`_iva_reachability_probe`, called from `validate_ledger_iva_aggregation_binding_definition`, with `_IvaReachabilityProbeObservation` carrying the five axes the matcher reads. When `cash_accounting_treatments` is empty the probe offers `NONE` — the treatment an ordinary non-cash-accounting row carries — so it asks the fairest available question of an empty selector and still gets a refusal.

No probe was added to the four families where it would be tautological. Adding one to each would have satisfied the Step's wording while manufacturing four more instruments that cannot fail; the honest limit is recorded instead, in the prior occupant's own docstring and as an executable assertion under `S08`.

## Verification

The whole registry corpus still validates: 3702 passed across the registry and renta suites, so the probe admits every binding that ships.
