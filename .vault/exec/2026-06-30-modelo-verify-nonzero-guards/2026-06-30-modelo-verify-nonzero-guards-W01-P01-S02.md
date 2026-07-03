---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S02'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Author the identical implies_nonzero(["04", "13"]) ADVISORY predicate on the 2023-2024 revision after re-confirming its base-imponible-previa formula text is byte-identical to 2025-y-siguientes

## Scope

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2023-2024/verification_expectations/0002-verification_predicates.toml`

## Description

- Read `formulas/0004-modelo-202-2023-2024-base-imponible-previa.toml` verbatim and confirm `13 = 04 + 38 - 39` is structurally byte-identical to `2025-y-siguientes` (`subtract(add(casilla_id=04, casilla_id=38), casilla_id=39)`); confirm both casillas `04` and `13` exist on this revision.
- Author the identical `modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo` ADVISORY `implies_nonzero(["04", "13"])` predicate as a new fragment, leaving the existing `0001-modelo-202-2023-2024-cuota-chain-verification.toml` workbook-parity file untouched.

## Outcome

New fragment `verification_expectations/0002-verification_predicates.toml` ships under `2023-2024` carrying the identical ADVISORY predicate as `2025-y-siguientes`. Formula text re-confirmation found NO divergence: byte-identical across all three revisions. Verified by the registry-shape test `test_committed_modelo_202_guards_base_imponible_previa_under_declaration[2023-2024]` and the parametrized gate-behaviour tests in `test_verification_m202_advisory.py`.

## Notes

No incidents. The plan's flagged open item (formula-text re-confirmation for the older revisions) is resolved: confirmed identical, no divergence handling needed.
