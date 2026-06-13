---
tags:
  - '#exec'
  - '#core-authority'
step_id: S11
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P04.S11 — Move OUTPUT_LANGUAGE_ENV_VAR to external_constants (RELOC-001)

## Change

Moved `OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANGUAGE"` from
`src/aeat/core/i18n/_render.py` to `src/aeat/core/external_constants.py`.

Added import in `_render.py`: `from ..external_constants import OUTPUT_LANGUAGE_ENV_VAR`.
Consumer import paths via `core.i18n` and `core.i18n._render` continue to work.

## Verification gate

Full i18n test suite — passed sequentially.

## Commit

Committed as part of W03.P04 i18n constant centralisation block.
