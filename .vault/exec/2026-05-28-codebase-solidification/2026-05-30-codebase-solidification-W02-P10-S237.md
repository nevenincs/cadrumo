---
step_id: S237
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S237

## Outcome

Created `src/aeat/domain/calculations/registry/test_casilla_field_kind_enrollment.py` with `@pytest.mark.unit @pytest.mark.domain_model` test `test_no_bare_kind_strings_survive_in_affected_files`. The test greps all four affected source files for surviving bare-string comparison and assignment patterns using four regex patterns covering `field.kind == "..."`, `case "...":`, `"kind": "..."` dict literals, and `kind="..."` keyword arguments. Comment-only lines are excluded to avoid false positives on inline docs. Test passes green confirming all bare-string sites are eradicated.

## Test result

1 passed (enrollment test alone); all targeted modules pass.

## Files touched

- `src/aeat/domain/calculations/registry/test_casilla_field_kind_enrollment.py` — created (new file, 93 lines)
