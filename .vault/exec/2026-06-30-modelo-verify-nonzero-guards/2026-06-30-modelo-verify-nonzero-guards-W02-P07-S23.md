---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S23'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-m210-categorical-conditional-predicate-adr]]"
---

# When outcome (a) was selected, append the M210 inmobiliaria-branch predicate using the new operator to the 2025 verification_predicates.toml and ship its two-tier test pair, FIRES when tipo_renta is inmobiliaria and valor_catastral is blank, HOLDS otherwise, or close this Step immediately with a one-line exec record cross-referencing the deferral

## Scope

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml`

## Description

- Appended the `modelo-210-2025-inmobiliaria-implica-base-imponible` ADVISORY predicate to the 2025 revision's `verification_expectations/0001-verification_predicates.toml`, using `casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])`, grounded in `legal_refs = ["trlirnr-rdleg-5-2004:art-13.1.h", "trlirnr-rdleg-5-2004:art-24"]` (art. 13.1.h for the Spanish-source imputed-rent classification, art. 24 for the base imponible determination), appended alongside the pre-existing untouched representante-fiscal and rendimientos-integros predicates.
- Authored an inline TOML comment block recording the full grounding chain: the `m210-base-imponible-2025` formula authority, every inmobiliaria input casilla being `required = false`, the `_evaluate_m210_resolve_base_imponible` raise case (both `valor_catastral` and the acquisition/administrative substitute absent), and the genuinely silent failure mode (a blank `dias_imputacion` with a valid `valor_catastral`/`coeficiente_imputacion_inmobiliaria` resolving `catastral_value * coefficient * 0` with no validation error).
- Chose the general shape ("inmobiliaria implies a non-zero `base_imponible`") over the narrower framing in the plan Step's literal text ("`valor_catastral` is blank"): the broader `casilla_equals_implies_nonzero` condition catches every zero-`base_imponible` path on the inmobiliaria branch, including the `dias_imputacion`-blank case the ADR's Considerations section identifies as the genuinely silent one, which a `valor_catastral`-only framing would miss. This is a deliberate, ADR-grounded refinement of the plan Step's illustrative wording, not a narrower implementation.
- Verified `trlirnr-rdleg-5-2004:art-13.1.h` is already defined in the legal catalogue (`src/aeat/_data/registry/aeat/legal/irnr.toml`) with a `corpus_ref` resolving to the bundled TRLIRNR consolidated text, so no new legal-catalogue entry was required.
- Added `test_modelo_210_2025_inmobiliaria_branch_carries_categorical_conditional_advisory` to `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py` (registry-shape tier): asserts the full three-predicate set on the loaded 2025 snapshot, the new predicate's exact expression string, `finding_kind == "ADVISORY"`, both `legal_refs`, that `tipo_renta` and `base_imponible` are real casillas on the revision, and cross-checks the art-13.1.h legal entry's `corpus_ref` and bundled-corpus text via `verify_legal_catalogue`.
- Extended `src/aeat/application/modelo/tests/test_verification_m210_advisory.py` (gate-behaviour tier) with four new tests covering the inmobiliaria guard: legal-grounding assertion, FIRES (`tipo_renta="inmobiliaria"`, zero `base_imponible`), HOLDS (`tipo_renta="inmobiliaria"`, positive `base_imponible`), and trivial-HOLD for both a non-matching `tipo_renta` and an entirely absent `text_values` mapping -- mirroring the FIRES/HOLDS/trivial-HOLD contract of every other Wave `W01` gate-behaviour suite.
- Confirmed the pre-existing `m210-representante-fiscal-required` (BLOCKING_RULE) and `modelo-210-2025-rendimientos-integros-implica-base-imponible` (ADVISORY) predicates are unmodified by this addition (both registry-shape and gate-behaviour tests assert the full predicate set, not just the new member).

## Outcome

The M210 inmobiliaria branch -- the campaign's highest-value silent-under-declaration gap -- now carries a non-blocking, legally grounded ADVISORY guard. The 2025 revision's `verification_predicates` array carries three predicates total (representante-fiscal BLOCKING_RULE, rendimientos-integros-to-base-imponible ADVISORY, inmobiliaria-to-base-imponible ADVISORY), all coexisting without mutual interference. Registry-shape and gate-behaviour tests both pass.

## Notes

No incidents. Outcome (a) was selected at `S20`/`S21`, so the "otherwise close this Step immediately" deferral branch was not exercised. The FIRES condition implemented is intentionally broader than the plan Step's illustrative "`valor_catastral` is blank" wording, per the ADR's own grounding that a narrower framing would miss the `dias_imputacion`-blank silent-zero path; this deviation is recorded here for the closeout audit.
