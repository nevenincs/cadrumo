---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Rename the aeat-prefixed temp work-area and secret prefixes to cadrumo across the five sites

## Scope

- `src/cadrumo temp prefixes`

## Description

- Rename `_DEFAULT_TEMPFILE_PREFIX = "aeat-secret"` to `"cadrumo-secret"` and its
  docstring mention in `_materialisation.py`.
- Rename `TemporaryDirectory(prefix="aeat-workbook-")` to `"cadrumo-workbook-"` and
  `TemporaryDirectory(prefix="aeat-xls-conversion-")` to `"cadrumo-xls-conversion-"`
  in `_workbook_parity.py`.
- Rename `TemporaryDirectory(prefix="aeat-review-package-")` to
  `"cadrumo-review-package-"` in `_review_package.py`.
- Rename `TemporaryDirectory(prefix="aeat-scale-bench-")` to
  `"cadrumo-scale-bench-"` in `test_ledger_scale_benchmark.py`.
- Sweep the mirrored `aeat-secret` literals in the traversal-safety fixture table
  of `test_materialisation.py` to `cadrumo-secret`.
- Confirmed no remaining `aeat-secret|aeat-workbook|aeat-xls-conversion|aeat-review-package|aeat-scale-bench`
  hits under `src` or `docs`.

## Outcome

All five sites renamed hard-cut (no aliasing) per ADR ruling R4. Targeted
`test_materialisation.py` suite (13 tests) passes; `ruff check` clean on all
touched files; full-tree `pytest --collect-only -q` collects cleanly
(12815 collected, 2745 deselected, exit 0). Committed at `c54367f318`.

## Notes

No literal in this step participates in a derived id, fingerprint, or
idempotency key -- these are ephemeral tempfile/tempdir prefixes only, unlinked
or removed at context exit. No incidents.
