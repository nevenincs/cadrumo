---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-28"
modified: '2026-07-17'
body_hash: 'sha256:6425c60fdd705aa005e7914d0d5ff135b7faface9ed853f2de2f3c20d8165dfc'
step_id: "S184"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S184 — real-behavior encoding alias map tests

## Outcome

Created `src/aeat/domain/calculations/registry/test_record_spec.py` with
13 real-behavior tests:

Direct alias-map contract (10 tests): assert each of the nine map entries
returns the correct canonical value, plus an idempotency-of-all-values test
(every canonical value is itself a key in the map), and an unknown-encoding
pass-through test.

Schema integration (2 tests): construct a real `ExportLayoutDefinition`
with `"latin-1"` and `"iso-8859-1"` records — asserts the validator accepts
the alias mix. A second test constructs `"cp1252"` + `"iso-8859-15"` and
asserts `ValidationError` with `"inconsistent encodings"`.

No mocks, no skips, no tautological assertions. Expected values are derived
from the AEAT codec-alias contract, not from the map itself.

86 tests pass in the targeted suite.

## Commit

`0ed384302`
