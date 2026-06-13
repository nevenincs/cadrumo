---
step_id: S169
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S169 — CasillaFieldKind StrEnum promotion

## Outcome

Added `CasillaFieldKind(StrEnum)` enum (8 members: LITERAL, CASILLA, BINDING, COMPUTED,
DRAFT, FILLER, HEADER, CHECKSUM) to `src/aeat/domain/calculations/registry/_schema.py`,
following the `InputKind` / `BeforeValidator` pattern from commit `1bff7b70f`.

Added `_coerce_casilla_field_kind()` validator and `CasillaFieldKindValue` annotated type.

Updated `ExportFieldDefinition.kind` from `Literal["literal", "casilla", ...]` to
`CasillaFieldKindValue`. Updated all 7 `_validate_field_kind` comparisons from bare
strings to `CasillaFieldKind.*` members.

Exported `CasillaFieldKind` and `CasillaFieldKindValue` from `__init__.py` (both import
block and `__all__`). Also added missing `InputKind` / `InputKindValue` to `__all__`
(ruff F401 cleanup).

Note: `_schema.py` changes were absorbed into peer commit `0ed384302` (S181-S184
file-extension centralisation). `__init__.py` changes are in commit `8381a5f9a`.

## Sibling bare-string sites

14 bare-string `.kind == "casilla"` etc. comparisons found across `_export.py`,
`_export_parse.py`, `test_*.py`, and `_validate_exports.py`. These remain working
because `StrEnum.__eq__` preserves string equality. Migration of call sites is a
separate follow-up; the typed boundary is now enforced at schema ingest.

## Commit

`8381a5f9a` (`__init__.py` export); `0ed384302` absorbed `_schema.py` edits.
