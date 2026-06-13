---
step_id: S303
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-iota6
commit: ae373e0f4
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P13.S303

Appended MIME-type constant tests to `src/aeat/core/test_external_constants.py`:
- `test_json_mime_type_value` — pins value to "application/json"
- `test_csv_mime_type_value` — pins value to "text/csv"
- `test_json_mime_type_is_final_str` / `test_csv_mime_type_is_final_str` — type checks
- `test_declarations_uses_json_mime_constant` — import identity check via importlib
- `test_tabular_export_uses_csv_mime_constant` — import identity check via importlib
- `test_no_bare_json_mime_literal_in_declarations` — AST scan anti-tautology proof
- `test_no_bare_csv_mime_literal_in_tabular` — AST scan anti-tautology proof

All 60 tests in focused run passed.
