---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S62'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update ledger UX defect tests for central redaction of identifiers

## Scope

- `src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py`

## Description

- Validate ledger UX defect-cluster CLI tests against the centralized output-redaction path.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_ledger_allocate_classification.py src/aeat/entrypoints/cli/test_ledger_validation_paths.py src/aeat/entrypoints/cli/test_ledger_ux_defect_cluster.py` passed: 41 passed.

## Notes

- The only emitted warnings were third-party `ofxparse` BeautifulSoup deprecation warnings; no test was skipped or xfailed.
