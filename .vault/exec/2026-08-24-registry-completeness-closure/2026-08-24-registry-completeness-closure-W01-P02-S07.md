---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:02ba6dc79037705283c8422f9fd056846cc3885b05ebf20bf3955ee994d17aee'
step_id: 'S07'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Compose the temporal coverage and authority-grade limb from validated law-selected registry revisions

## Scope

- `src/cadrumo/application/registry/`

## Description

- Add a strict temporal evidence report with one row for every loaded modelo revision.
- Derive each row's filing coordinate from its declared selector, reselect it through `inspect_revision`, and reject any identity mismatch.
- Request the validated snapshot at exactly the selected revision's declared authority grade; retain ungraded and refused cases as explicit rows.
- Expose the report through the application-registry facade and add focused real-authority coverage.

## Outcome

The temporal limb now preserves the entire registered revision denominator. A row is validated only when its selector reselects the same revision without a revision-id override and its declared grade is accepted by the snapshot boundary. The direct Modelo 036 applicability exercise selected revision `2025-02-03-y-siguientes` and returned a validated row.

Verification passed:

- `uv run --no-sync python -c "... compose_temporal_coverage(...)"` — real validated authority exercise passed.
- `.venv/Scripts/python.exe -m pytest -n 0 -q src/cadrumo/application/registry/tests/test_temporal_coverage.py` — 2 passed in 26.33s.
- `uv run --no-sync ruff check src/cadrumo/application/registry/_temporal_coverage.py src/cadrumo/application/registry/__init__.py src/cadrumo/application/registry/tests/test_temporal_coverage.py` — passed.

## Notes

The shared pytest runner started the focused test serially and its process completed, but the host did not return the final summary. A subsequent isolated bounded run captured the passing result above. No registry data, grade, temporal selector, or export capability was changed.
