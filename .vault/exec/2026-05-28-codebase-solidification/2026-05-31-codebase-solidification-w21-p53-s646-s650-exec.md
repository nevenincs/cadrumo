---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S646
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W21.P53.S646-S650

Landed 5 Steps closing P53: parameter-Any rationale markers across wizard/Google-adapter sites plus a new AST-walk ratchet and aggregate closure test.

- Modified: `src/aeat/core/profile.py`
- Modified: `src/aeat/core/profile_catalogue.py`
- Modified: `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`
- Modified: `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`
- Created: `src/aeat/test_any_param_rationale_inventory.py`
- Created: `src/aeat/test_w21_p53_closure.py`

## Description

S646: Added `KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR` above both `Any`-annotated parameter sites in `core/profile.py` — the `ProjectAnswersFn.__call__` protocol method and the module-level `project_answers()` proxy function — documenting the circular-import barrier between `aeat.core` and `aeat.application.wizard`.

S647: Added `KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR` above `register_wizard_catalogue()` in `core/profile_catalogue.py`, referencing the same circular-import rationale.

S648: Added `ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE` above every function carrying an untyped `Any` parameter in the Google outbound adapters:
- `_calc_sheets_apply.py`: 5 sites (`_find_folder`, `_create_folder`, `_ensure_folder`, `_find_spreadsheet`, `_create_spreadsheet`) — all `drive: Any` / `sheets: Any` Google Resource objects.
- `_calc_sheets_pull.py`: 4 sites (`_coerce_value`, `_row_set_block_range`, `_decode_row_set_block`, `_decode_row_set_cell`) — `raw: Any` (untyped Google Sheets cell) and `row_set: Any` (circular import barrier).

S649: Created `test_any_param_rationale_inventory.py` — AST-walk ratchet that prevents parameter-`Any` drift in all production files under `src/aeat/`. Walker checks `FunctionDef`/`AsyncFunctionDef` parameter annotations for bare `Any` or generics containing `Any`. Sites with one of the three marker tokens in the preceding 3 lines are exempt. Allowlist (`_KNOWN_VIOLATING_LINES`) seeds 30 pre-existing sites. Test passes at authoring time; new sites without a marker fail immediately.

S650: Created `test_w21_p53_closure.py` — aggregate closure test (11 sub-tests) verifying marker presence in all target files, S649 ratchet importability and green pass, and 6 prior-wave ratchets (utf8, cast-rationale, latin1, enum-constant, mock, no-skip-xfail) all green.

## Verification

- Grep-post: `KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR` — 2 hits in `core/profile.py`.
- Grep-post: `KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR` — 1 hit in `core/profile_catalogue.py`.
- Grep-post: `ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE` — 5 hits in `_calc_sheets_apply.py`, 4 hits in `_calc_sheets_pull.py`.
- pytest: 12 tests pass (1 ratchet + 11 closure).
- Commit: `8157f6ff4`
- S649 allowlist size: 30 pre-existing parameter-Any sites.
