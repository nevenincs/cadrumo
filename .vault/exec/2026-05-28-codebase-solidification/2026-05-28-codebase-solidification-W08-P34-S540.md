---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S540'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S540`

INVENTORY TEST: Real-behavior test asserting zero bare `"iso-8859-1"` string literals in the BOE export test package, enforcing the `LATIN_1_ENCODING` enrollment landed in S532.

- New: `src/aeat/test_w08_p34_latin1_inventory.py`

## Description

The test walks `src/aeat/adapters/outbound/aeat/export/` recursively, collecting every `test_*.py` file, and fails with a descriptive assertion if any line contains the bare `"iso-8859-1"` literal. This provides a CI-enforced regression gate that prevents future reintroduction of bare encoding strings. No mocks, no skips, no tautological conditions — the collection function returns real violations from real file reads.

Marked `pytest.mark.unit` and `pytest.mark.domain_core`.

## Tests

`test_no_bare_iso8859_1_in_export_test_package` passed with 0 violations after S532 enrollment. The test would have failed on the pre-S532 state (20+ violations).
