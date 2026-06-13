---
step_id: S494
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S494

**Step**: use LATIN_1_ENCODING as dict key in _record_spec.py:16 and document latin_1 codec alias.

## Outcome

- `_record_spec.py` imports `LATIN_1_ENCODING` from `external_constants`
- `ENCODING_ALIAS_MAP` key `"latin-1"` → `LATIN_1_ENCODING`
- `_LATIN_1_CODEC_ALIAS: Final[str] = "latin_1"` added as named constant for the Python codec alias at line 17

## Files

- `src/aeat/domain/calculations/registry/_record_spec.py`

## Commit

5b45dd58c
