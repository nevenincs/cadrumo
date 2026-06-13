---
tags:
  - '#exec'
  - '#core-authority'
step_id: S14
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P05.S14 — Replace AEAT_GROI_URL with lazy Settings read (RELOC-004)

## Change

Removed module-scope `AEAT_GROI_URL = AnyUrl(Settings.external_constants().aeat.oracles.groi_check)`
constant from `domain/calculations/registry/_groi_oracle.py` and its re-export from
`domain/calculations/registry/__init__.py`.

Replaced all five call sites with lazy `Settings.external_constants().aeat.oracles.groi_check`
reads at actual use time (in `planned_operations`, navigate, and error context).

Updated test files (`test_groi_oracle.py`, `test_groi_check.py`, `test_groi_check_live.py`)
to compute URLs via `Settings.external_constants()` rather than importing the removed constant.

Removed `AEAT_GROI_URL` from `adapters/outbound/aeat/sede/_groi_check.py` import and `__all__`.

## Verification gate

`pytest src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/adapters/outbound/aeat/sede/test_groi_check.py -q` — passed sequentially.

## Commit

Committed as part of W03.P05 URL constant lazy-reads block.
