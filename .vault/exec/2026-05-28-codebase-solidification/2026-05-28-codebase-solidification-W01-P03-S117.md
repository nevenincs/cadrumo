---
step_id: S117
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S117 — introduce DEFAULT_OUTPUT_LANGUAGE constant

## Outcome

`src/aeat/core/i18n/_render.py` now declares:

```python
DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es"
```

Both `"es"` fallbacks in `_cached_output_language` are routed through this
constant:

- `except (KeyError, ValueError, AttributeError): return DEFAULT_OUTPUT_LANGUAGE`
- `return _normalise_supported_language(...) or DEFAULT_OUTPUT_LANGUAGE`

`DEFAULT_OUTPUT_LANGUAGE` added to `__all__`. `from typing import Final` import
added. Commit `1926f5cc4`.

## Files touched

- `src/aeat/core/i18n/_render.py`

## Verification

`vault plan step check S117` applied. All tests pass.
