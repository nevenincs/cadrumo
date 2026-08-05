---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:02ce0b3aa5b910485a61d449340292f5f81f92b4500a33122b9f4b8ca8b8b5ba'
step_id: 'S19'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express and ## Scope

- `src/cadrumo/domain/invoices/_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Measure the registry's Spanish numeric IVA rate coverage directly from `rates.toml` (bypassing the enum) and confirm the served window starts 2024-01-01, carrying exactly `general/21`, `reduced/10`, `super_reduced/4`, `zero/0`.
- Confirm `IvaRate`'s numeric slots (`RATE_0`, `RATE_4`, `RATE_10`, `RATE_21`) already equal that set; no enum member is missing and no unresolvable member exists, so no enum change ships.
- Add a parity gate under the invoices domain test folder asserting `numeric_iva_rate_percentages()` equals the registry's numeric ES rate set for the served window, and a companion assertion over rate kinds.
- Add a mutation-proof test demonstrating the equality comparison discriminates: perturbing either the registry-side or enum-side set by one member flips agreement to disagreement, so the gate is not vacuously true.
- Pin the `RATE_5` absence as an explicit invariant test tied to the registry carrying no matching rate for the served window.

## Outcome

Registry-vs-enum agreement confirmed both independently (raw TOML parse) and through the loaded `IvaRateRecord` table: both declare `{0, 4, 10, 21}` for Spain across the served window (2024-01-01 onward, continuous through the open-ended 2025 window). No enum member was added or removed. Landed `src/cadrumo/domain/invoices/tests/test_rate_parity.py` with four tests: numeric-percentage parity, numeric-kind parity, the RATE_5-absence invariant, and the mutation-discrimination proof. Full invoices test folder plus the IVA rate-table tests (138 tests) pass.

## Notes

No production code changed; the Step's gap premise (a missing 5% enum member) was disproven at HEAD before implementation began, so the deliverable narrowed to the parity gate the ADR's corrected ruling calls for. Two files were left untouched though touched by peer work in the same working tree during discovery (`src/cadrumo/domain/iva/_components.py`, `src/cadrumo/domain/invoices/_decomposition.py`) — out of this Step's scope and not committed here.
