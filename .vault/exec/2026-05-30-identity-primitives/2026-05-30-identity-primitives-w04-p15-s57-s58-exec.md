---
step_id: S57, S58
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W04.P15 — lift CLI payload modules onto registry aliases

## Scope

Phase W04.P15 sweeps the bare-string registry-id BaseModel fields
across the CLI modelo payload surface onto the typed registry
aliases declared in `domain/calculations/registry/_ids.py` per
ADR Rule 8. The CLI payload module is the wire boundary that
emits modelo command JSON; strict-pydantic discipline applies.

## Outcome

`src/aeat/entrypoints/cli/_modelo_payloads.py` — Step S57:
- Added registry alias import (`CasillaId`, `FormulaId`,
  `RevisionId`).
- Lifted BaseModel fields onto aliases:
  - `WorkUnitPayload.revision_id` → `RevisionId`
  - `ObservationPayload.casilla_id` → `CasillaId`,
    `ObservationPayload.formula_id` → `FormulaId | None`
  - `ResultSummaryRowPayload.casilla_id` → `CasillaId`
  - `FindingPayload.casilla_id` → `CasillaId | None`
  - `FormulaPayload.formula_id` → `FormulaId`
  - `WorkCreateResult.revision_id` → `RevisionId`
  - `WorkStatusResult.revision_id` → `RevisionId`
  - `WorkRenameResult.revision_id` → `RevisionId`
  - `WorkDiscardResult.revision_id` → `RevisionId`

Step S58 (residual CLI payload modules): ripgrep of
`src/aeat/entrypoints/cli/` for bare-string casilla_id /
formula_id / revision_id / modelo_id / binding_id on
pydantic-BaseModel field declarations returned zero hits
after S57 — the residual sites listed in the reference doc
are either typer arguments (function signatures, out of
Rule 9 clause 4) or already typed through W03.P12.S53 and
W03.P13.S54. S58 closed empty.

## Skipped per brief discriminator

- Filter fields (`bucket_id_filter`, `work_unit_id_filter`,
  `calculation_revision_id_filter`) stay bare-str: operator
  filter input accepts non-canonical references per Rule 7's
  reference-vs-mint discriminator.
- Reference tuples (`operand_refs`, `legal_refs`, `source_refs`,
  `input_casillas`, `input_bindings`, `input_parameters`,
  `input_relations`, `resolved_casillas`,
  `missing_required_casillas`) stay `tuple[str, ...]`: lifting
  to alias tuples would reject operator-supplied collection
  references per W02.P07 brief precedent.
- `expectation_id`, `reference_id` stay bare-str (no alias
  exists for these identities yet).

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/` — 898
  passed, 83 pre-existing failures (modelo-period-consistency
  CLI refusals, profile-lifecycle wizard catalogue gaps,
  apoderado scoping drift) per brief catalogue. Spot-checked
  one failure (`test_work_calculate_confirms_the_draft_was_saved`)
  — REFUSED_CLI_VALIDATION_BOUNDARY originates upstream of the
  payload-construction surface (verified by tracing the error
  envelope to the input parsing path, not the OutputSchema
  validation path).
- Smoke import test on all 9 modified modules passes cleanly.

## Plan steps closed

`W04.P15.S57`, `W04.P15.S58`.

## Commits

- `8d5d2cc79` exec(identity-primitives): W04.P15.S57 lift CLI
  modelo payload registry-id fields onto registry aliases
- (S58 closed as empty — no commit)
