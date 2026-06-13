---
name: modelo-303-390-phase1-task1
description: Execution record — Modelo 303 + Modelo 390 builders, schemas, validator extension, unit tests (#62)
type: exec
tags:
  - "#exec"
  - "#modelo-303-390"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-modelo-303-390-plan]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-modelo-303-390-research]]"
---

# modelo-303-390 phase1 task1

Issue: wgergely/aeat#62
Branch: `feature/62-modelo-303-390`

## Work performed

- Added `src/aeat/application/filing/_builders/_modelo_303_schema.py`
  (static casilla collection, 27 casillas covering IVA devengado
  general regime, IVA deducible, resultado de la liquidación).
- Added `src/aeat/application/filing/_builders/_modelo_390_schema.py`
  (static casilla collection, 15 casillas: ejercicio, 10
  quarterly-sum annual totals, 4 intra-390 aggregates).
- Added `src/aeat/application/filing/_builders/modelo_303.py`
  (`Modelo303Builder`, fixed-point formula resolver mirroring
  the Modelo 130 pattern, Google-style docstrings, strict
  coercion helpers).
- Added `src/aeat/application/filing/_builders/modelo_390.py`
  (`Modelo390Builder`, quarterly 303 draft tuple ingestion via
  reserved `_quarterly_303` inputs key, INHERITED provenance on
  quarterly-sum casillas, COMPUTED provenance on the four
  intra-390 aggregates, shape-validation of the four quarterly
  drafts).
- Extended `src/aeat/application/filing/_builders/__init__.py` registry to
  include `Modelo303Builder` and `Modelo390Builder`.
- Extended `src/aeat/application/filing/_validator.py` with an additive
  `quarterly_303_drafts` kwarg and a new
  `_validate_quarterly_reconciliation` rule that emits two new
  finding codes (`filing-390-303-mismatch`,
  `filing-303-internal-mismatch`) with trilingual
  (`es`/`en`/`hu`) `Translatable` messages. The 130 and 303
  validation paths are unchanged.
- Extended `src/aeat/application/filing/__init__.py` so `build_draft`
  forwards the four quarterly drafts into the validator when the
  target modelo is 390 and exports `Modelo303Builder` /
  `Modelo390Builder` / `QUARTERLY_303_INPUT_KEY` on the public
  API.
- Extended `src/aeat/application/filing/testing.py` so
  `default_schema_provider()` wires the 130/303/390 collections
  and the module re-exports `MODELO_303_SCHEMA` /
  `MODELO_390_SCHEMA`.
- Added `src/aeat/application/filing/test_modelo_303_390.py` — 21 colocated
  unit tests (`@pytest.mark.unit`) covering:
  - Modelo 303 happy path (21% only) with hand-calculated
    casilla values.
  - Modelo 303 happy path with all three IVA rates.
  - Default-rate casillas carried as `FilingValueKind.DEFAULT`.
  - Missing-required-casilla (casilla `07` with
    `defaulted=False`) emits an ERROR finding.
  - Out-of-range finding on casilla `65`.
  - Formula-divergence finding when a computed casilla is
    tampered via `model_copy`.
  - Stable `draft_id` across two builds (303 and 390).
  - JSON round-trip via `model_dump_json` /
    `model_validate_json` (303 and 390).
  - Builder registration via `build_draft` dispatch.
  - Modelo 390 quarterly shape validation (missing drafts,
    wrong count, wrong year, missing ejercicio).
  - Modelo 390 clean reconciliation (no mismatch findings).
  - Modelo 390 → 303 mismatch finding (tampered annual value).
  - Modelo 390 303 self-consistency finding (tampered
    quarterly cuota).
  - Trilingual message keys present on mismatch findings.

## Gate results

All gates green on Windows:

- `just lint` → ruff + format passed.
- `just typecheck` → ty passed.
- `just test` → 586 passed, 1 skipped (the pre-existing
  skip), 18 deselected. The 21 new tests all pass.
- `just hooks` → prek passed all hooks (ruff, ruff-format, ty,
  trim-whitespace, end-of-files, yaml/toml, large-files,
  merge-conflict, private-key).

## Notes for reviewer

- The 303 casilla schema helper `_base` takes a `defaulted: bool`
  kwarg so casilla `07` (the most-common 21% base) is the
  single required-without-default casilla. That exercises the
  required-missing validation code path in the unit tests
  without breaking the happy path where only `07` is supplied.
- The 390 builder uses `FilingValueKind.INHERITED` for its 10
  quarterly-sum casillas — semantically correct, and sidesteps
  the existing formula-trace validator rule which is in-draft
  only.
- The validator's reconciliation rule compares decimals with a
  `Decimal("0.005")` tolerance to absorb cent-level drift, and
  is gated on `draft.modelo == "390"` + a populated
  `quarterly_303_drafts` tuple so the 130/303 paths remain a
  no-op.
- `validate_draft` does NOT thread the quarterly drafts into
  its re-validation call — the rule is skipped there because
  we do not have the quarterlies in hand. Tests that need to
  re-run the rule construct a `FilingValidator` directly. A
  follow-up can extend `validate_draft` with an explicit
  `quarterly_303_drafts` kwarg once #23 lands.
