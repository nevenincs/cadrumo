---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:3d2b56ae9219b81ba9d16c449bfafe04b1a8796353a0980c77da0632c8026b65'
step_id: 'S07'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Disposition the class-C window-but-no-seed modelos as seed rules or advisories.

## Scope

- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

- Audit the class-C window-but-no-seed set (123, 232, 322, 353, 360, 369) against the current `_MODELO_APPLICABILITY_RULES` table; find 123 (payer-fact), 322 and 353 (IVA-group enrolment) already seed-ruled in the baseline.
- Add the `OSS_ENROLLED` member to the `PayerFact` enum in `_applicability_payer_facts.py` and wire its predicate to the determinable `profile.iva.oss_enrolled` boolean.
- Add the Modelo 369 (ventanilla única OSS/IOSS) seed rule to `_applicability.py`, enrolment-gated on `PayerFact.OSS_ENROLLED`, with `applicable_entity_types = _PAYER_FACT_ENTITY_TYPES` and legal grounding.
- Add the OSS Spanish incomplete-label to `PAYER_FACT_INCOMPLETE_LABELS` in `_applicability_labels.py` so an undeclared enrolment produces the grounded undetermined rationale.
- Update the canonical ruled-modelo pin in `test_modelo_applicability.py` to include 369.

## Outcome

- Modelo 369 legal grounding: `orden-hac-610-2021:art-1` (aprobación del modelo 369), `orden-hac-610-2021:art-2` (obligados a presentar, BOE-A-2021-10161, corpus-backed with required_text "Estado miembro de identificación sea España"), and — since the generic OSS seed spans all three ventanilla-única regimes — the three LIVA ámbito articles `ley-37-1992:art-163-octiesdecies` (régimen exterior / no-Unión), `art-163-unvicies` (régimen de la Unión), and `art-163-quinvicies` (régimen de importación / IOSS). All resolve in the legal catalogue; the `test_seed_modelo_applicability_legal_refs_resolve_in_registry` gate confirms it. (Corrected per the M369 seed independent code review: the seed previously cited only `art-163-quinvicies`, which is the import/IOSS regime, mis-grounding the Union-regime population; it now cites all three ámbito articles.)
- Functional probe: an `oss_enrolled=True` profile resolves Modelo 369 to `APPLICABLE` (surfaces on the calendar); an `oss_enrolled=False` (or undeclared) profile resolves to `INCOMPLETE` (advised → investigate). This is the fail-closed enrolment-gated behaviour ADR Decision 3 ratified — never a false-positive seed for a taxpayer not enrolled.
- Modelos 232 (operaciones vinculadas) and 360 (devolución IVA no establecidos) are left advised-only: neither has a determinable `TaxpayerProfile` predicate, so per the fail-closed mandate they stay window-backed but seed-less, resolving to `INCOMPLETE` (advised) rather than a fabricated seed. The coverage total-partition test confirms they land in the advised bucket, never silently absent.
- Gates: registry collect-only clean (3150 collected, 0 errors); the full overview + applicability suites green (233 passed); referential-integrity and deadline-window-source-tier gates green (35 passed); ruff clean.

## Notes

- The class-C dispositions for 123/322/353 were already in the baseline; this Step added 369 and confirmed 232/360 as deliberate fail-closed advisories, closing the full class-C set.
- The OSS enrolment fact reuses the same bool-backed, no-tri-state pattern as the existing IVA-group enrolment facts (`IVA_GROUP_MEMBER` / `IVA_GROUP_DOMINANT_ENTITY`): an unset enrolment is treated as undetermined (INCOMPLETE/advised), not guessed to NOT_APPLICABLE, so the surface never silently drops a possibly-obliged filer.
