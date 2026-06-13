---
step_id: S231
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S231

## Outcome

Replaced the self-contained `_parse_boolean` at `src/aeat/domain/calculations/registry/_export_parse.py:409` with a thin wrapper that delegates to `aeat.core.parsing._utils._parse_bool` (imported as `_core_parse_bool`).

Design choice: **option (b) — thin wrapper** rather than extending the core helper. Rationale: the registry truthy set (`{"X", "S", "SI"}`) uses uppercase AEAT-specific affirmative markers that are not part of the generic cross-domain core set. Encoding those into core would leak domain knowledge downward. The wrapper normalises to lowercase before consulting `_REGISTRY_TRUTHY` / `_REGISTRY_FALSY` module-level frozensets, then delegates to `_core_parse_bool` for any token neither set covers, and finally raises `RegistryValidationError` for genuinely unrecognised tokens. All two existing call-sites (`lines 243, 371`) remain unchanged.

## Files touched

- `src/aeat/domain/calculations/registry/_export_parse.py` — import `_core_parse_bool`, add frozensets, replace helper body
