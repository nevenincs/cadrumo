---
step_id: S53
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S53 — hoist _registry.py logger to module level

## Outcome

Replaced the inline `import logging as _logging` + `_logging.getLogger(__name__).debug(...)`
in `resolve_output_language` with a module-level `logger = _logging_stdlib.getLogger(__name__)`
and `logger.debug(...)`.

Circular-import investigation: `aeat.core.logging.get_logger` calls
`configure_logging()` which lazily imports `aeat.core.config` which imports
`aeat.core.errors.CoreValidationError`. Since `_registry.py` is part of
`aeat.core.errors` (loaded during its `__init__`), calling `get_logger` at
`_registry.py` module level triggers the cycle. The safe fix is to use
`logging.getLogger(__name__)` directly — the stdlib getter imposes no eager
config — and alias it as `_logging_stdlib` to avoid the name `logging` being
shadowed. The root-level `SecretScrubbingFilter` installed by
`configure_logging()` propagates to this logger via normal logger hierarchy
propagation.

## Files touched

- `src/aeat/core/errors/_registry.py`

## Verification

`uv run --no-sync python -c "import aeat.core.errors._registry; print('OK')"` — OK.
`uv run --no-sync pytest src/aeat/core/errors/test_registry.py -xvs -k "not sphinx_role and not broken_fragments"` — 7 passed.
(Deselected tests fail due to pre-existing `es.yml` special-character WIP from a parallel campaign — not introduced by this step.)
`vault plan step check S53` applied.
