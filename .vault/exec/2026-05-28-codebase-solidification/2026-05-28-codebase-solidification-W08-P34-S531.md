---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S531'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S531`

FIX: `NonTtyRefusedError.__init__` dropped the positional `message` arg to `super().__init__()` so the locale resolver uses the registry `message_key` instead of `args[0]`.

- Modified: `src/aeat/entrypoints/cli/_tty.py`
- New: `src/aeat/entrypoints/cli/test_tty_error_locale.py`

## Description

`AeatError.__init__` short-circuits locale resolution when `args` is non-empty — a positional `message` argument populated `args[0]` and bypassed the `message_key` lookup. The fix passes `suggestion` as a keyword argument only and lets `super().__init__()` leave `args` empty.

```python
def __init__(self, suggestion: str) -> None:
    super().__init__(suggestion=suggestion.strip() or None)
    self.suggestion: str = suggestion
```

Grep-post-condition: `grep -n "super().__init__(message" src/aeat/entrypoints/cli/_tty.py` returned 0 lines.

## Tests

`test_tty_error_locale.py` asserts: `exc.args == ()`, `exc.suggestion` is accessible, and locale key `errors.refused.refused_cli_non_tty` resolves to a non-placeholder string. All three assertions passed.
