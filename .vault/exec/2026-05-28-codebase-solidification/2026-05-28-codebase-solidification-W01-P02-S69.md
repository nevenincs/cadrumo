---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S69'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P02.S69`

Converted the fenced ```` ```python ```` block in `src/aeat/domain/normatives/__init__.py` to proper `>>>` doctest format. The original example was inside a docstring (not executable) but the fenced block style made the intent ambiguous. The doctest approach was chosen per the brief's stated preference and for consistency with S71.

- Modified: `src/aeat/domain/normatives/__init__.py`

## Description

Replaced the `Example:` block with `Example::` rst-style heading and `>>>` / `...` doctest lines. This makes the example unambiguously non-executable at module import while remaining runnable via `python -m doctest`.

## Tests

S70 covers this with a real subprocess import test. No stdout captured on import.
