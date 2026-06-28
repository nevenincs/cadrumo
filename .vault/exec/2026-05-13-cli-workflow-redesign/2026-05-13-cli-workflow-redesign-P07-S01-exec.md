---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S01 — sentence-case error prefix landed at the rendering boundary

## Finding

C-1 (CRITICAL). The previous P05.S05 step never reached the production
text-rendering path. `render_error_text` in
`src/aeat/core/errors/_registry.py` still built the stderr first line
from the raw uppercase enum value (`f"{prefix}: {message}"`), so live
stderr emitted `REFUSED: ...` despite the apex sentence-case mandate.

## Resolution

Added a `_TEXT_PREFIX: dict[ErrorCategory, str]` dispatch table to
`_registry.py` mapping every category enum to its sentence-case
operator-visible display string and replaced the inline
`code.category.value` lookup inside `render_error_text` with the table
lookup. The enum values themselves are unchanged, so the JSON envelope's
`category` field stays grep-stable (`"REFUSED"`, `"AUTH"`, etc.) while
the text first line now reads `Refused.`, `Error.`, `Auth.`,
`Integrity.`, `Failed.`, `Internal.`, `Locked.` respectively.

`test_error_boundary_integration.py` was updated to assert
`assert "Refused." in result.output`.
`test_core_error_prefixes_are_grep_stable` was rewritten to pin both
contracts: the structured JSON `"category":"LOCKED"` form is unchanged
AND the rendered text first line starts with the sentence-case
`Locked. ` / `Internal. ` literals.

## Verification

`pytest src/aeat/core/errors/ src/aeat/entrypoints/cli/test_error_boundary_integration.py`
runs green; the rendering boundary now emits the sentence-case prefix
on stderr for every category in the registry.
