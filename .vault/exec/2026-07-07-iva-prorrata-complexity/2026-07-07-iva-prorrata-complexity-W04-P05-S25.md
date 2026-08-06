---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:4ac6930124887e4b1084f8bd8aff4fd5ed9a160d10e924c74288cad1671d1cad'
step_id: 'S25'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Prove especial and sector apportionment fire from the operator flow: an anti-dormant end-to-end test that elects especial and declares sectors and tags inputs through the service the CLI calls then runs the live aggregation and asserts the especial and sector apportionment change the deducible cuota, with the non-electing path byte-identical

## Scope

- `src/aeat/application/aggregation/tests/test_prorrata_operator_ingress_end_to_end.py`

## Description

- Add an anti-dormant end-to-end test that drives the register write through the EXACT application service the `elect-especial` / `declare-sector` CLI verbs call (`ProrrataRegisterService.declare` / `.declare_sector`) and tags ledger rows with the `--sector` field (`prorrata_sector_id`), then runs the SAME production aggregation the live calculate path runs.
- Assert the especial apportionment fires: after electing especial through the service, the deducible cuota routes the three LIVA art. 106.Uno reglas (100/0/general) and differs from the whole-entity baseline.
- Assert the per-sector apportionment fires: after declaring two sectors + per-sector entries through the service and tagging rows, the deducible cuota routes each input at its sector percentage and differs from the whole-entity baseline.
- Assert the non-electing operator path (no service write) is byte-identical to the unapportioned aggregate.

## Outcome

The honesty-review HIGH is closed at the load-bearing point: the especial and sector apportionment engines, previously reachable only from tests seeding the raw adapter, now demonstrably fire from the operator `ProrrataRegisterService` the CLI verbs call. The proof is behavioral (result differs from the whole-entity baseline), not a spy, so a silent fallback to general would fail it. Three tests pass under `-n0`; expected values derive from the LIVA art. 106.Uno reglas and the art. 101 per-sector rule, never from the substrate under test.

## Notes

- Fixtures mirror the S15 especial-oracle fixture (base 50.00 / iva 10.50 / rate 0.21 / amount 60.50) because a 0.20 IVA rate is not a recognised Spanish rate and the aggregation does not classify it as soportado.
- The KEY distinction from S15/S20: those seed the register via `ProrrataRegisterRepository(...).save` (raw adapter); this drives `ProrrataRegisterService(...).declare` / `.declare_sector` — the exact operator-flow entry points — which is what makes the engines operator-reachable rather than test-only.
