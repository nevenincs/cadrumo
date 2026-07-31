---
step_id: S171
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-07-17'
body_hash: 'sha256:0cff3478b28325a165011df85b849463f3e9a2465fd2015675b4215bce26ec90'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S171 — extract CLASSIFIED_BY_MANUAL constant

## Outcome

Introduced `CLASSIFIED_BY_MANUAL: Final[str] = "manual"` in
`src/aeat/application/ledger/_models.py` and migrated all three bare-string
call-sites to reference it.

## Files changed

- `src/aeat/application/ledger/_models.py` — added `Final` to `typing` import;
  appended `CLASSIFIED_BY_MANUAL` constant after `BULK_CLASSIFY_ALLOWED_COLUMNS`.
- `src/aeat/application/ledger/__init__.py` — added `CLASSIFIED_BY_MANUAL` to
  the `_models` import block and `__all__`.
- `src/aeat/application/ledger/_actions.py` — imported `CLASSIFIED_BY_MANUAL`;
  replaced bare `"manual"` at lines 3059 and 3557.
- `src/aeat/entrypoints/cli/_ledger.py` — imported `CLASSIFIED_BY_MANUAL` from
  `application.ledger`; replaced bare `"manual"` at line 3325.

## Sites migrated

3 bare-string `"manual"` literals replaced (audit finding A7.6).

## Verification

`uv run --no-sync pytest src/aeat/application/ledger/test_models.py -xvs` — 10 passed.
