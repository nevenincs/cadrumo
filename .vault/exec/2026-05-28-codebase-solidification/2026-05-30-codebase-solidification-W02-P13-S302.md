---
step_id: S302
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-iota6
commit: ae373e0f4
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P13.S302

Migrated MIME-type literals to named constants:
- `_declarations.py:1248` `content_type="application/json"` → `content_type=_JSON_MIME_TYPE`
  (import: `from .....core.external_constants import JSON_MIME_TYPE as _JSON_MIME_TYPE`)
- `_tabular.py:69` `media_type = "text/csv"` → `media_type = _CSV_MIME_TYPE`
  (import: `from ...core.external_constants import CSV_MIME_TYPE as _CSV_MIME_TYPE`)
