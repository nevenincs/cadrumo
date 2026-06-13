---
step_id: S49
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S49 — _stdio.py logger constraint verification

## Outcome

`src/aeat/entrypoints/cli/_stdio.py` already uses `logging.getLogger(__name__)`
(stdlib) rather than `aeat.core.logging.get_logger`. The constraint comment at
lines 119-125 accurately documents why: `_stdio.py` runs at the top of CLI
startup before settings are loaded; calling `get_logger` would invoke
`configure_logging()` which pulls settings eagerly, creating a circular-import
risk at import time.

Scrubbing still applies at runtime: the stdlib logger propagates records to
root, and `configure_logging()` installs `SecretScrubbingFilter` on the root
logger. This propagation contract is verified by S50 tests.

No code change was required. The existing implementation satisfies the step's
"if unsafe, use stdlib and document" path.

## Files touched

- `src/aeat/entrypoints/cli/_stdio.py` — no change; constraint already documented

## Verification

`_LOGGER = logging.getLogger(__name__)` at line 125 with constraint comment
at lines 119-125. S50 tests confirm scrubbing applies via root propagation.
`vault plan step check S49` applied.
