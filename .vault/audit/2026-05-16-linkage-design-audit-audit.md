---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-16-linkage-design-audit-plan]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
---



# `linkage-design-audit` audit: `Wave 2 close-out: model consolidation`

## Scope

Wave 2 of the linkage-design epic. Targeted defect class T-04 from the
Issue Taxonomy v1 reference document: same-semantic-concept-multiple-
shapes. Built on Wave 1's type-system uniformity foundation.

Plan: 6 Phases (P01-P06), 25 Steps, L2 tier. All Steps closed.

## Findings

### Headline numbers

- Pydantic model inventory: **791 BaseModel subclasses** (789 at start
  of Wave 2; minor fluctuation from Phase work).
- Cross-package similarity pairs at Jaccard >= 0.5: **253 -> 251**.
- Name-collision duplicate count (post-dedup): **5 -> 4**
  (VerificationFinding resolved via rename).
- Three known duplicate families consolidated, each closing a
  specific F-finding from the linkage research record.
- ty check: **0 diagnostics** maintained throughout.
- pyright real-bug tier: **0** maintained.
- import-linter: 1 contract kept (no-renta-in-registry), 0 broken.

### Phase-by-phase

- **P01 (similarity-matrix triage)** - extended `pydantic_audit.py`
  with file-line deduplication (5 real name duplicates after
  filter, down from 56 raw). Dispatched Sonnet agent to classify
  253 similarity pairs into 9 CONSOLIDATE families, 31 PARALLEL
  pairs, 8 HIERARCHICAL pairs, 205 TEST_FIXTURE noise. Catalogue at
  `scratch/out/wave2_consolidation_catalogue.md`.
- **P02 (CCAA canonicalisation)** - canonical `CCAA` enum in
  `domain/profile/_ccaa.py` enhanced with `from_iso_code()` and
  `from_label()` class methods. `RentaCCAA` deleted. TOML
  dispatch-table tokens already matched the canonical enum
  value; no TOML migration needed. New semgrep rule
  `no-duplicate-ccaa-enum.yml` flags reintroduction.
- **P03 (Casilla schema unification)** -
  `RegistryCasillaSchema` promoted from a frozen dataclass with
  degraded types to a pydantic v2 strict/frozen model with typed
  IDs (`CasillaId`, `FormulaId`, `LegalRefId`, `SourceRefId`),
  `Decimal | None` numeric bounds, and full `legal_refs` /
  `source_refs` propagation. Defect F6 materially advanced.
- **P04 (observation-type layering)** - resolved defect F7 via
  Protocol-based dependency inversion. The Python constant
  `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` replaced with a local
  `frozenset` derived from the same TOML binding selectors.
- **P05 (similarity-matrix consolidations)** - addressed 5 of 9
  CONSOLIDATE families. 3 families deferred with rationale.
- **P06 (regression gates)** - new semgrep rule
  `no-duplicate-concept-models.yml`. Three layered import-linter
  contracts drafted and deferred (real production violations
  block activation; Wave 3 prerequisites).

## Recommendations

1. **Wave 3 scope** - the typed-envelope promotion (defect class
   T-01) is the highest-leverage outstanding work. Replacing
   `Mapping[str, Decimal]` on `RegistryFilingObservation`,
   `RegistryCalculationResult`, and `CalculationRevision` with a
   typed `CasillaObservation` envelope closes the canonical drop
   site at `application/modelo/_actions.py:817`.
2. **Referential integrity gate** (T-09) - implement
   `_check_all_id_references` as a pydantic `model_validator` on
   `RegistrySnapshot`. Closes 0 / 21 ID type coverage in one
   implementation.
3. **Discriminated selector unions** (T-02) - promote
   `DataBindingDefinition.selector` to a discriminated union of
   per-source pydantic models.
4. **Hexagonal-direction enforcement** - resolve the three
   deferred forbidden contracts by refactoring the offending
   production paths in `domain.deadlines`, `domain.profile._keys`,
   `core.errors`, and `core.i18n._render`.
5. **Hand-authored data and registry referential integrity**
   (T-12) - BOE record specs in
   `adapters/outbound/aeat/export/_formats/` should gain
   structural pytest coverage.
6. **Operator-visible legal grounding** - now that
   `RegistryCasillaSchema` carries `legal_refs`, adopt the
   `--explain` flag convention in CLI emit paths.
