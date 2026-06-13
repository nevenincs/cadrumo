---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S155'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P06.S155`

Remove the empty `if TYPE_CHECKING: pass` block from `_taxation_comparison.py`. The block contained no imports or comments — only a bare `pass` — making it dead code left by an earlier refactor. The `TYPE_CHECKING` import was removed alongside it.

- Modified: `src/aeat/application/modelo/_taxation_comparison.py`

## Description

Lines 35-36 (`if TYPE_CHECKING: pass`) were deleted. The `TYPE_CHECKING` symbol imported from `typing` was also removed since it was only referenced by the dead block. The `Literal` type used in `_run` remains; the `from typing import Literal` import was kept.

## Tests

No tests needed for a deletion-only change. S156 covers the import-clean verification gate. Commit SHA: 74f07401b.
