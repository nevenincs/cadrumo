---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:1760fd7d7e41ccdb00d39e2127fa91c3a240958848c8fb1b5526c240f792bf5e'
step_id: 'S187'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P07.S187

Extract `"COLUMNS"` env-key literal to `_COLUMNS_ENV_VAR: Final[str]` module constant.

- Modified: `src/aeat/entrypoints/cli/_stdio.py`

## Description

Added `from typing import Final` import and introduced `_COLUMNS_ENV_VAR: Final[str] = "COLUMNS"` constant after `_MIN_HELP_RENDER_COLUMNS`. Replaced both `os.environ.get("COLUMNS")` and `os.environ["COLUMNS"] = ...` call sites in `_ensure_help_render_width` with `os.environ.get(_COLUMNS_ENV_VAR)` and `os.environ[_COLUMNS_ENV_VAR] = ...` respectively, eliminating the naked string literals as flagged by audit finding A7.11.

## Tests

No production-logic change; existing test suite passes. S188 adds dedicated coverage for the constant and its usage paths.
