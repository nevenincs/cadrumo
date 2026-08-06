---
step_id: S456
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:574e617b6146741cead0c534f67e895a0b6e94118694659c87c681a741a1a996'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S456

## Step

Enroll `_PDF_EXTENSIONS` local frozenset at `application/ledger/_evidence.py:41` to use `PDF_EXTENSION` from `external_constants`.

## Outcome

- Added `from ...core.external_constants import PDF_EXTENSION` import.
- Changed `_PDF_EXTENSIONS = frozenset({".pdf"})` to `_PDF_EXTENSIONS = frozenset({PDF_EXTENSION})`.
- Import ordering fixed by ruff.
- 9 tests in `test_evidence.py` pass.

## Files touched

- `src/aeat/application/ledger/_evidence.py`
