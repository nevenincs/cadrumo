---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Author the modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo ADVISORY predicate implies_nonzero(["04", "13"]) with legal_refs ley-27-2014:art-40-3 and ley-27-2014:art-40, grounded in the 2025-y-siguientes 13 = 04 + 38 - 39 formula confirmed during plan authoring

## Scope

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/verification_expectations/0002-verification_predicates.toml`

## Description

- Confirm casillas `04` and `13` exist on the `2025-y-siguientes` M202 revision and that `13` is formula-derived from `04` via `13 = 04 + 38 - 39` (`formulas/0004-modelo-202-base-imponible-previa.toml`).
- Confirm both legal_refs (`ley-27-2014:art-40-3`, `ley-27-2014:art-40`) already resolve in `legal/is.toml`.
- Author the `modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo` ADVISORY `implies_nonzero(["04", "13"])` predicate as a new fragment, leaving the existing `0001-modelo-202-2025-cuota-chain-verification.toml` workbook-parity file untouched.

## Outcome

New fragment `verification_expectations/0002-verification_predicates.toml` ships under `2025-y-siguientes` carrying one ADVISORY predicate. Verified by the registry-shape test `test_committed_modelo_202_guards_base_imponible_previa_under_declaration[2025-y-siguientes]` and the gate-behaviour tests in `test_verification_m202_advisory.py` parametrized for this revision (authored together with S02-S05; see those records for the full multi-revision test suite).

## Notes

No incidents. No legacy compatibility shim involved; this is a pure registry-authoring addition with no schema change.
