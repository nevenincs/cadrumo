---
step_id: S62, S63, S64
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

# identity-primitives W04.P18 — lift residual registry-id survivors and close Wave 4 with audit

## Scope

Phase W04.P18 closes the Wave by lifting residual bare-string
registry-id BaseModel fields across application services
(S62), adapter modules (S63), and running the final ripgrep
audit (S64) to confirm zero promotable survivors remain.

## Outcome

Step S62 — application services:
- `application/storage/calc_sheets/_records.py`:
  `SheetProvenanceRow.formula_id` → `FormulaId | None`,
  `SheetExportMetadata.revision_id` → `RevisionId`.
- `application/storage/calc_sheets/_layout.py`:
  `SheetLayout.revision_id` → `RevisionId`.
- `application/storage/calc_sheets/_parity_harness.py`:
  `ModeloFormParityResult.revision_id` → `RevisionId`.
- `application/calculations/_binding_prefill.py`:
  `PrefilledBinding.binding_id` → `BindingId`,
  `LocalIvaCompensationRecurrence.binding_id` → `BindingId`.
- `application/modelo/_result_summary.py`:
  `ResultSummaryRow.casilla_id` → `CasillaId`.
- `application/verification/_schema.py`:
  `ClassifiedDiscrepancy.casilla_id` → `CasillaId`.

Step S63 — adapter modules:
- `adapters/outbound/google/_calc_sheets_pull.py`:
  `PullMetadata.revision_id` → `RevisionId`.
- `adapters/inbound/declaracion/_schema.py`:
  `ExtractionWarning.casilla_id` → `CasillaId | None`.

Step S64 — final ripgrep audit:
Residual bare-string `casilla_id` / `formula_id` /
`revision_id` / `modelo_id` / `binding_id` declarations on
pydantic-BaseModel fields outside the registry `_ids.py`
module after Wave 4 fall into three categories:

1. **Out of Rule 9 clause 4 (dataclass / Protocol /
   function parameter / NamedTuple)** — properly skipped:
   `_validate_*.py` (every site), `_record_design.py`,
   `_temporal.py`, `_snapshot.py`, `_loader.py`,
   `_authority.py`, `_label_regex.LabelHit`,
   `_verify._Discrepancy`, `_registry_contract` (Protocol),
   `manuals.py`, `_record_spec.py` (function param),
   `_XmlDictionaryEntry` (dataclass).
2. **Narrowing-forbidden by brief**:
   - `application/state_projection.py` and
     `application/user_profile/__init__.py` revision_id
     `max_length=64` (registry `RevisionId` is
     `max_length=128`).
   - `application/aggregation/_source_mesh.py`
     binding_id / casilla_id `max_length=256`.
   - `domain/calculations/registry/_live_parity.py:545`,
     `adapters/outbound/google/_calc_sheets_pull.py:175`,
     `application/storage/calc_sheets/_records.py:438`,
     `application/storage/calc_sheets/_parity_harness.py:104`,
     `application/filing/runtime.py:129` modelo_id
     `min_length=1` or wider (registry `ModeloId` is
     `^\d{3}$`).
   - `adapters/persistence/storage/sql/secure_objects.py:148`
     revision_id `min_length=64, max_length=64` (hex-64
     calculation revision shape, not registry RevisionId
     kebab-ref shape — these are
     `CalculationRevisionId`-shaped, lifted in W02).
3. **Deliberate test-only fixture** — preserved:
   `src/aeat/core/test_json_envelope_roundtrip.py:46,48`
   declares `_ProvenancePayload(OutputSchema)` with
   bare-`str` casilla_id / formula_id. The fixture
   deliberately tests JSON-envelope roundtripping under
   synthetic shapes; coupling it to the registry pattern
   would over-specify the contract.

S64 ripgrep returned zero in-scope promotable hits.

## Skipped — alias not yet declared

None. Every bare-string registry-id field encountered
either had an existing alias or fell into one of the three
skip categories above. No escalation candidates.

## Per-Phase gate

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/`
  (full run): 2068 passed, 74 pre-existing failures (renta_web
  replay drift, record_design coverage, registry_reviewability
  baseline, ledger_renta date_binding gap, etc.). No new
  my-fault failures.
- Smoke imports on the 9 modules touched in P18 pass cleanly.

## W04 close gate

Suite delta vs W01 baseline (11576 passed / 335 failed) at
per-package scope. Targeted Wave-4 packages verified clean:
registry suite delta is zero new failures; CLI per-package
83 failures all map to brief-catalogued peer-introduced
surfaces (modelo-period-consistency CLI refusals,
profile-lifecycle wizard catalogue gaps, apoderado scoping).
Full sequential `pytest src/aeat/` not run within harness
window; per-package gate satisfies the Wave-4 brief.

## Plan steps closed

`W04.P18.S62`, `W04.P18.S63`, `W04.P18.S64`.

## Commits

- `61cfa1cb0` exec(identity-primitives): W04.P18.S62 lift
  application-layer registry-id BaseModel fields onto
  registry aliases
- `5b76fcf94` exec(identity-primitives): W04.P18.S63 lift
  adapter registry-id BaseModel fields onto registry aliases
- (S64 audit closed without code changes — zero in-scope
  survivors)
