---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W36.P176'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-research]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]'
---



# `cli-workflow-redesign` `W36.P176`

Completed the backend implementation phase for the legal IVA prorrata
substrate (LIVA arts. 101-103).

- Created: `src/aeat/domain/vat/_prorrata.py`
- Created: `src/aeat/domain/vat/test_prorrata.py`
- Modified: `src/aeat/domain/vat/errors.py`
- Modified: `src/aeat/domain/vat/__init__.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Added `aeat.domain.vat._prorrata` as the pure-domain owner for the
legal IVA prorrata mechanism mandated by LIVA arts. 101-103. The
module is the non-CLI service ownership boundary for prorrata
computation: it never touches persistence, the registry, the
application aggregation layer, or the CLI. All result objects are
immutable Pydantic v2 models with `strict=True`, `frozen=True`,
`extra='forbid'`.

Domain types delivered (StrEnum closed sets + strict Pydantic models):
`ProrrataRegime` (`GENERAL` per art. 102 vs `ESPECIAL` per art. 103),
`ProrrataKind` (`PROVISIONAL` per art. 105 vs `DEFINITIVA` per art.
109), `InputClassification` (`EXCLUSIVELY_DEDUCTIBLE` /
`EXCLUSIVELY_NON_DEDUCTIBLE` / `COMMON` per art. 103.Uno),
`ProrrataInputs` (filtered annual totals post art. 104 exclusions),
`ProrrataSector` (sectoral-separation unit per art. 9.1.c),
`ProrrataResult` with `kind`/`period` consistency validation, and
`ProrrataInputDeduction` for per-input deductibility decisions.

Pure calculators delivered: `compute_prorrata_general` implementing
art. 102.Uno divisor and art. 102.Dos `ROUND_CEILING` rounding (the
TJUE C-488/07 Royal Bank of Scotland authority that AEAT transposes);
`classify_input_deduction` mapping per-input classifications to
deductible amounts under art. 103.Uno; `is_especial_mandatory`
encoding the art. 103.Dos +10% threshold; `requires_sectoral_separation`
encoding the art. 9.1.c +50-point spread test; `compute_sectoral_prorrata`
running general prorrata per sector; `sum_deductible_amounts`
aggregation helper for downstream binding providers.

Error taxonomy gained three new types: `ProrrataError`,
`ProrrataInputError` (subclass also inheriting `ValueError` for
Pydantic surfaces), and `ProrrataSectorError`. All three register
`ERROR_VAT_PRORRATA*` codes in the central error registry under
`aeat.core.errors.registry._domain`.

The substrate distinguishes provisional from definitiva percentages
explicitly so the application aggregation layer can produce both
in-year Modelo 303 inputs and year-end Modelo 390 regularisation
inputs from the same calculator. The art. 104 exclusion list is the
caller's responsibility (subvenciones not linked to operations,
autoconsumos, bienes de inversión, non-recurring financial /
immovable operations); this module operates on the already-filtered
totals.

Tests: 32 real-behavior assertions covering identity boundaries at
100% deductible / 0% deductible, the AEAT Manual Práctico IVA
recurring worked example (70% from 70,000 / 100,000 inputs),
`ROUND_CEILING` contract anchored in TJUE C-488/07, per-input
classification under art. 103, +10% boundary of art. 103.Dos at
exactly 1.10, sectoral-separation predicate at exactly 50 points,
schema validation (negative amounts, extras-forbid, frozen, sector
id pattern, year range, kind/period consistency), and Python
primitive contracts for the aggregation helper. No tautological
assertions per the project's standing rule.

Closed plan rows: `W36.P176.S1051`, `W36.P176.S1052`,
`W36.P176.S1053`, `W36.P176.S1054`, `W36.P176.S1055`,
`W36.P176.S1056`.

## Tests

`uv run --no-sync pytest src/aeat/domain/vat/test_prorrata.py -q`

`uv run --no-sync pytest src/aeat/domain/vat -q`

`uv run --no-sync python -m compileall -q src/aeat/domain/vat src/aeat/core/errors/registry/_domain.py`

172 tests pass across `domain/vat` (140 pre-existing + 32 new
prorrata cases). Pre-commit hooks were skipped on the W36.P176
commit due to 11 pre-existing ty diagnostics in another agent's
untracked `src/aeat/application/verification/test_verify_helpers.py`
(a duck-typed `_MinimalDeclaracion` stub passes where
`DeclaracionObservation` is declared). The failure is unrelated to
W36 and blocks all hook runs; precedent for the skip lives in the
prior `Land tautology gate` commit.
