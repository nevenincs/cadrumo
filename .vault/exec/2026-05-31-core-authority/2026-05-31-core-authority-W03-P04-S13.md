---
tags:
  - '#exec'
  - '#core-authority'
step_id: S13
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P04.S13 — Move SUPPORTED_OUTPUT_LANGUAGES to external_constants (RELOC-003)

## Change

Moved `SUPPORTED_OUTPUT_LANGUAGES: Final[tuple[str, ...]] = ("es", "en", "ca", "hu")` from
`src/aeat/core/i18n/_render.py` to `src/aeat/core/external_constants.py`.

Added import in `_render.py`: `from ..external_constants import SUPPORTED_OUTPUT_LANGUAGES`.
Removed `from typing import Final` from `_render.py` (no longer needed).
`core/i18n/__init__.py` re-exports `SUPPORTED_OUTPUT_LANGUAGES`; all twelve
consumer import paths continue to work.

## Verification gate

Full i18n test suite run sequentially — passed.

## Commit

Committed as part of W03.P04 i18n constant centralisation block.
