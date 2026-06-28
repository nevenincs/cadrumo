---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s94-explicit-route-guard-exec]]'
---

# `secure-storage-production-hardening` `W12.P23.S94` Explicit Route Guard Review

## S94-EXPLICIT-ROUTE-001 | MEDIUM | RESOLVED | Guard initially skipped shared test helpers

The first review found that the explicit-route guard classified test surfaces only by test-file naming, which skipped shared test helpers such as `src/aeat/tests/secure_sql.py`. The guard now scans shared `/tests/` helper modules and includes `secure_sql.py` in the approved explicit-route allowlist.

## S94-EXPLICIT-ROUTE-002 | LOW | RESOLVED | Detector initially missed embedded env-line constants

The first review found that the detector matched exact string constants and f-string constants but would miss executable strings such as `AEAT_DATABASE_URL=...`. The detector now matches embedded `AEAT_DATABASE_URL` and `aeat_database_url` executable string constants while ignoring docstring-only narrative mentions.

## S94-EXPLICIT-ROUTE-003 | PASS | Fixed guard accepted

The re-review passed. Scoped validation passed: 7 guard tests passed, ruff passed, and whitespace checks passed.

Residual risk: the allowlist is file-level, so approved files can add additional explicit-route setup without a new guard failure. S95 must constrain those approved files with a human-readable ownership inventory.
