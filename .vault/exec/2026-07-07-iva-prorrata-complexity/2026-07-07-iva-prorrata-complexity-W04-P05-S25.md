---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S25'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S25 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Prove especial and sector apportionment fire from the operator flow: an anti-dormant end-to-end test that elects especial and declares sectors and tags inputs through the service the CLI calls then runs the live aggregation and asserts the especial and sector apportionment change the deducible cuota, with the non-electing path byte-identical and ## Scope

- `src/aeat/application/aggregation/tests/test_prorrata_operator_ingress_end_to_end.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
