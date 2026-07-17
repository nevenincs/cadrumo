---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S413'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# emit per-socio M184 verify/file handoff info Notices carrying the attributed Modelo184MemberRow values and the exact socio-side profile-capture command

## Scope

- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Add `m184_socio_handoff_notices(revision)` to `_modelo_rendering.py`: filter the revision's `detail_rows` to `Modelo184MemberRow`, and emit one info Notice per socio carrying the attributed value (nif/nombre/importe), a `suggestion` = the exact fold-in command `aeat app modelo work calculate --binding 1577=<importe>` onto the relation-canonical casilla 1577, and `context` with target_casilla + arts. 86-89 legal_refs. Returns `[]` for any revision without member rows.
- Wire the helper into the M184 `work verify` and `work file` emit points in `_modelo_work_verification_cli.py`, loading the revision via `load_calculation_revision` to reach `detail_rows`, and extend the `notices` list before `_emit_envelope`.
- Add unit coverage: two-socio fire (message + suggestion + context assertions), silent-without-member-rows, and silent-for-non-M184-detail-rows (proves the helper filters on the typed row, not any detail row).

## Outcome

Committed via the S413 explicit-pathspec retry (SHA on the coordinator STOP report). Gates green (-n0): 3 handoff tests + the verify/file integration flow (28 passed, the 1 unrelated failure is a `work calculate` arg-validation test outside this surface, amid heavy peer WIP); ruff + ty clean. Completes the m184 decision-(a) slice end-to-end: S411 (facts) + S413 (M184-side handoff Notice with the exact fold-in command) + S414 (M100-side omission advisory) + the manual `--binding` how-to.

## Notes

- Scope corrected from the plan's stale `cli/_modelo.py` ref (a Typer registration hub with no verify/file handler body) to the real emit points `_modelo_work_verification_cli.py` (`work verify` + `work file`), confirmed by the coordinator. This is the "stale `_modelo.py` line-refs" the #197 reconciliation flagged — the second grounding catch in this slice after the S412 casilla-1577 collision.
- The helper + test were polished in place (target casilla 1577, arts. 86-89, the exact `--binding` command) to fully realise the ADR's "exact socio-side command"; the enhancement is a superset of the original and stays ADR-faithful (decision (a): 1577 relation-canonical, cross-bucket value entered by hand).
- No collision: cdc-coder's m210 S03 keyed on `_calculate_input.py`, not these CLI files.
