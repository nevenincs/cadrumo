---
tags:
  - '#plan'
  - '#linkage-design-audit'
date: '2026-05-16'
modified: '2026-05-16'
tier: L2
related:
  - '[[2026-05-15-linkage-design-audit-research]]'
  - '[[2026-05-15-linkage-design-audit-reference]]'
  - '[[2026-05-15-linkage-design-audit-audit]]'
  - '[[2026-05-15-linkage-design-audit-plan]]'
  - '[[2026-05-26-linkage-design-audit-adr]]'
---
# `linkage-design-audit` `Wave 2: model consolidation (Phase 2 of linkage epic)` plan

### Phase `P01` - similarity-matrix triage and consolidation catalogue

Dispatch deep analysis of the pydantic-audit output to separate
genuine duplicate-concept candidates from coincidental field overlap.
Produce a prioritised consolidation catalogue at
`scratch/out/wave2_consolidation_catalogue.md` naming each duplicate
family, its canonical-target shape, and its migration cost estimate.

- [x] `P01.S01` - extend pydantic audit tool to dedupe by file-line and emit a refined catalogue; `scratch/pydantic_audit.py`.
- [x] `P01.S02` - dispatch Sonnet agent to triage 253 similarity pairs into duplicate families; `scratch/out/wave2_consolidation_catalogue.md`.
- [x] `P01.S03` - validate the catalogue against the research record's three known duplicate families; `scratch/out/wave2_consolidation_catalogue.md`.

### Phase `P02` - CCAA canonicalisation

Pick one canonical CCAA enum and migrate. Likely target: a new typed
alias `CCAA` declared once in `domain/profile/_ccaa.py` with both ISO
short codes and Spanish names as aliases. Delete the other two.

- [x] `P02.S04` - draft canonical CCAA pydantic / enum shape; `src/aeat/domain/profile/_ccaa.py`.
- [x] `P02.S05` - migrate RentaCCAA call sites with libcst codemod; `src/aeat/domain/renta/_substrate.py`.
- [x] `P02.S06` - migrate dispatch-table call sites in the registry TOML; `registry/aeat/modelos/100/revisions/2025.toml`.
- [x] `P02.S07` - remove the obsolete RentaCCAA enum; `src/aeat/domain/renta/_substrate.py`.
- [x] `P02.S08` - add import-linter forbidden contract preventing reintroduction of duplicate CCAA shapes; `.importlinter`.

### Phase `P03` - Casilla schema unification

Adopt `CasillaDefinition` as canonical. Replace
`RegistryCasillaSchema` projection with one that preserves typed IDs,
Decimal bounds, and legal_refs. Either keep the `CasillaSchema`
Protocol but tighten its contract or remove it.

- [x] `P03.S09` - upgrade RegistryCasillaSchema to preserve typed IDs and legal_refs; `src/aeat/application/filing/runtime.py`.
- [x] `P03.S10` - tighten CasillaSchema Protocol contract; `src/aeat/domain/filing/_protocols.py`.
- [x] `P03.S11` - migrate filing consumers to read legal_refs from the projection; `src/aeat/application/filing/`.
- [x] `P03.S12` - add structural test asserting legal_refs survive projection; `src/aeat/application/filing/test_runtime.py`.

### Phase `P04` - observation type layering fix

Move `RentaDeductibleExpenseObservation` from `domain/renta/` to
`application/aggregation/` so the calculations registry no longer
imports across domain packages. Resolves F7 architectural-boundary
violation flagged in the research record.

- [x] `P04.S13` - move RentaDeductibleExpenseObservation into the aggregation layer; `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `P04.S14` - replace registry binding import with the new location; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P04.S15` - add import-linter forbidden contract for domain.calculations to domain.renta; `.importlinter`.
- [x] `P04.S16` - eliminate RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS constant and move mapping to registry TOML; `src/aeat/domain/renta/_ledger_expenses.py`.

### Phase `P05` - similarity-matrix consolidations

Address the remaining duplicate families surfaced by P01 catalogue.
Step list is added dynamically by `vault plan step add` as each family
is triaged. Expect roughly 5-15 additional duplicate families with
varying consolidation cost.

- [x] `P05.S17` - placeholder for first triaged duplicate family; `scratch/out/wave2_consolidation_catalogue.md`.
- [x] `P05.S21` - consolidate ProfileExportBundle onto UserProfilePortableExport (domain); `src/aeat/domain/user_profile/_values.py`.
- [x] `P05.S22` - rename VerificationFinding name collision: modelos -> ModeloVerificationFinding, evidence -> EvidenceBundleCheckResult; `src/aeat/domain/modelos/_verification_report.py`.
- [x] `P05.S23` - reclassify WorkUnitHistoryEvent/BucketEvent as HIERARCHICAL; `WorkUnitHistoryEvent is an intentional projection stripping bucket_id and payload_version; `src/aeat/application/modelo/_history.py`.
- [x] `P05.S24` - add PullMetadata.to_sheet_export_metadata() projection bridge onto canonical SheetExportMetadata shape; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [x] `P05.S25` - add OperatorEdit.to_operator_input() projection bridge onto canonical OperatorInput shape; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.

### Phase `P06` - regression gates for shape duplication

Add semgrep rule flagging new pydantic models whose name matches an
existing canonical concept across packages. Add import-linter
`forbidden` contracts preventing reconstruction of deprecated shapes.

- [x] `P06.S18` - add semgrep rule flagging duplicate-name candidates; `.semgrep/rules/no-duplicate-concept-models.yml`.
- [x] `P06.S19` - extend import-linter contracts to prevent regression; `.importlinter`.
- [x] `P06.S20` - close out Wave 2 by re-running pydantic audit; `scratch/out/pydantic_audit/`.
