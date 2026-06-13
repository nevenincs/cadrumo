---
step_id: S104
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P30.S104 step record

## Step

Migrate all production `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")`
local declarations to `from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN`.
(MERGE014-001, Rule 10)

## Migration count

- **84 files migrated** (83 from initial grep + 1 discovered during cleanup).
- **2 bespoke files excluded** (retain local ConfigDict with `arbitrary_types_allowed=True`):
  - `adapters/persistence/storage/bucket/_layout.py`
  - `adapters/persistence/storage/sql/secure_objects.py`
- **1 file already migrated** prior to this step: `domain/attachments/_models.py`

## Verification

```
grep -rln "_STRICT_FROZEN = ConfigDict" src/aeat/ --include="*.py"
```

Returns exactly 2 files (the 2 bespoke modules above).

Identity placement diagnostics: 21 passed in 11.17s (no regressions).

All 1684 Python files parse without SyntaxError.

## Approach

Automated migration script replaced `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")`
with `from {relative_dots}core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN`,
then cleaned unused `ConfigDict` from pydantic import lines. Bespoke variants
(arbitrary_types_allowed, validate_assignment, extra="allow") were left in place.
Inline `model_config = ConfigDict(...)` declarations with the standard pattern
were also migrated.

## Files touched

84 production files across adapters/, application/, core/, and domain/ packages.
