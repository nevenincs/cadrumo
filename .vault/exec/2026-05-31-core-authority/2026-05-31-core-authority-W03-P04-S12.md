---
tags:
  - '#exec'
  - '#core-authority'
step_id: S12
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P04.S12 — Move DEFAULT_OUTPUT_LANGUAGE to external_constants (RELOC-002)

## Change

Moved `DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es"` from
`src/aeat/core/i18n/_render.py` to `src/aeat/core/external_constants.py`.

Added import in `_render.py`: `from ..external_constants import DEFAULT_OUTPUT_LANGUAGE`.
`DEFAULT_OUTPUT_LANGUAGE` is not re-exported from `core/i18n/__init__.py`; callers
that use `from ..core.i18n._render import DEFAULT_OUTPUT_LANGUAGE` continue to work
since `_render.py` still exposes it as a module attribute (via import).

## Verification gate

Full i18n test suite — passed sequentially.

## Commit

Committed as part of W03.P04 i18n constant centralisation block.
