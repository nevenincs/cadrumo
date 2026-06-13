---
tags:
  - '#audit'
  - '#code-duplication-sweep'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-code-duplication-sweep-research]]"
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
title: "Retirement and Rename Residue Audit"
source: "Automated Codebase Scanning with Regex and Manual Verification"
relevance: 9
---

# Retirement-Residue Audit: May 19, 2026

## Executive Summary

Comprehensive audit of the src/aeat codebase for structural residue from recently-landed retirement and rename campaigns. The project lead clarified that "retire" means COMPLETE DELETION with no shims, aliases, deprecation markers, or legacy re-exports.

**Result**: CLEAN. No residue violations found.

---

## Audit Scope

### Items Checked

1. **Legacy Borrador Service** (retired from src/aeat/application/live/_borrador.py):
   - BorradorService
   - BorradorPrefillEntry
   - _derive_snapshot_id (legacy form)

2. **WorkUnitNotFoundError Consolidation** (_actions.py canonical, removed from _reconcile.py):
   - Duplicate class elimination

3. **CCAA Rename** (_festivos.py → CalendarCCAA; profile._ccaa.py → CCAA):
   - Alias residue check

4. **ModeloRepository Rename** (core/resources → StaticModeloRepository; persistence/sql → ModeloRepository):
   - Alias residue check

5. **StorageError Rename** (outbound storage → OutboundStorage* family):
   - Alias residue check

6. **Deprecation Tooling**: DeprecationWarning, warnings.warn, @deprecated decorators, # DEPRECATED, # TODO: remove/deprecate, # legacy comments

7. **Shim Modules**: One-liner re-export files

8. **Test Residue**: Function/class names referencing deleted identifiers

9. **Documentation Residue**: Docstrings referencing deleted classes

10. **Locale/CLI Strings**: Help text and locale keys referencing retired items

---

## Findings by Category

### A. Compat/Alias Residue

**Status**: CLEAN

**Checks Performed**:
- Regex: ^(BorradorService|BorradorPrefillEntry|WorkUnitNotFoundError|CCAA|ModeloRepository|StorageError)\s*=
- Verified all module-level imports and exports in __init__.py files
- Checked for from X import Y as Z patterns in all retirement-target modules

**Result**: NO aliases found. All identifiers are either:
1. Fully deleted (BorradorService, BorradorPrefillEntry, legacy _derive_snapshot_id)
2. Canonically defined in one location only (WorkUnitNotFoundError in _actions.py)
3. Properly namespaced without collision (CCAA in profile, CalendarCCAA in deadlines)
4. Contextually distinct without aliasing (ModeloRepository in sql, StaticModeloRepository in core/resources)
5. Properly prefixed by boundary (OutboundStorageError in outbound, StorageError in persistence)

### B. Deprecation Tooling Residue

**Status**: CLEAN

**Checks Performed**:
- Regex: DeprecationWarning|warnings\.warn|@deprecated|deprecated:|# DEPRECATED|TODO.{0,20}(remove|deprecate)|# legacy|# LEGACY
- Manual review of all matches

**Findings**:
1. src/aeat/domain/calculations/registry/_validate.py:2526: warnings.warn(...) — registry validation warning (acceptable; unrelated to retirements)
2. src/aeat/application/ledger/_ratios.py:137: Comment "legacy on-disk records that bypass validation on read" — refers to historical database records, not code retirement
3. src/aeat/application/live/_snapshot_base.py:5-6: Docstring "file-based legacy services" — design documentation for Phase 3 migration; not a deprecation marker

**Conclusion**: No deprecation markers for any retired identifiers. The above are legitimate design documentation or validation warnings, not residue.

### C. Shim Modules

**Status**: CLEAN

**Checks Performed**:
- Regex: ^from.*import \*$
- Manual audit of __init__.py files in retirement-target packages
- Verification that all imports are genuine re-exports (acceptable for package facades) or legitimate implementation imports

**Result**: NO shim modules found. All imports serve a real architectural purpose:
- src/aeat/application/live/__init__.py properly imports and exports Borrador100* classes (canonical forms only)
- src/aeat/application/modelo/__init__.py imports WorkUnitNotFoundError from _actions.py (single canonical source)
- All storage and deadlines __init__.py files export their canonical types without re-export-only shims

### D. Locale/CLI Residue

**Status**: CLEAN

**Checks Performed**:
- Regex (case-insensitive): borrador_service|BorradorService|workunitnotfound|ccaa|storage_error
- Scanned: src/aeat/locales/ and src/aeat/entrypoints/cli/

**Findings**:
- Locale keys reference tax-residence-ccaa (refers to the profile CCAA type; correct usage)
- No string keys reference borrador_service, BorradorService, workunitnotfound, or deprecated storage names
- All CCAA references in locale strings use the correct profile-layer identifier

### E. Test Residue

**Status**: CLEAN

**Checks Performed**:
- Regex: test_borrador_service|TestBorradorService|test.*work_unit_not_found.*reconcile|test.*BorradorService
- Verified existing test files reference only canonical classes

**Findings**:
- src/aeat/application/live/test_borrador_100.py — tests canonical Borrador100Snapshot (not legacy service)
- src/aeat/application/live/test_borrador_100_roundtrip.py — same, canonical form
- src/aeat/application/modelo/test_borrador_binding.py — tests modelo borrador binding (not legacy service)
- src/aeat/application/modelo/test_reconcile.py — correctly imports WorkUnitNotFoundError from _actions

**Pycache Note**: Stale .pyc files in src/aeat/application/live/__pycache__/ reference:
- _borrador.cpython-313.pyc
- test_borrador.cpython-313.pyc

These are build artifacts from deleted source files. No action required; they are not part of the source code.

### F. Documentation Residue

**Status**: CLEAN

**Checks Performed**:
- Regex (multiline): """[^"]*BorradorService[^"]*""", raises.*BorradorSnapshotNotFoundError
- Manual review of docstrings in _snapshot_base.py, _borrador_100.py, _actions.py

**Findings**:
- src/aeat/application/live/_snapshot_base.py:47-50: Docstring "Per-service subclasses (BorradorSnapshotNotFoundError, ...)" — correctly documents the canonical exception hierarchy
- No docstrings reference deleted classes BorradorService or BorradorPrefillEntry
- All error documentation references canonical exception classes from _snapshot_base.py and _borrador_100.py

---

## Verification of Consolidations

### WorkUnitNotFoundError Consolidation

**Canonical Location**: src/aeat/application/modelo/_actions.py

**Verification**:
- Only ONE class definition: line 159 of _actions.py
- Inheritance: class WorkUnitNotFoundError(ModeloError, KeyError)
- Exported in __all__ at line 2453 of _actions.py
- Re-exported in src/aeat/application/modelo/__init__.py at line 87
- Correctly imported in _reconcile.py at line 27: from ._actions import WorkUnitNotFoundError
- No duplicate definition in _reconcile.py

**Conclusion**: Consolidation complete and clean.

### Legacy Borrador Service Deletion

**Previous File**: src/aeat/application/live/_borrador.py (now deleted)

**Canonical Successor**: src/aeat/application/live/_borrador_100.py

**Verification**:
- File listing: _borrador.py does not exist in src/aeat/application/live/
- No imports of _borrador module found (except stale pycache)
- All references to Borrador100 classes import from _borrador_100.py
- Exports in src/aeat/application/live/__init__.py (lines 27-35) reference only _borrador_100 classes

**Conclusion**: Legacy file deleted; no residual imports or shims.

---

## Zero-Finding Conclusion

**Grand Total**:
- **Aliases Found**: 0
- **Deprecation Markers Found**: 0 (related to retirements)
- **Shim Modules Found**: 0
- **Locale Residue**: 0
- **Test Residue**: 0
- **Documentation Residue**: 0

The retirement and rename campaigns have been executed cleanly with zero structural residue. The codebase is compliant with the project lead's mandate: complete deletion with no shims, aliases, deprecation markers, or legacy re-exports.

---

## Attestation

**Audit Date**: 2026-05-19
**Audit Method**: Automated regex scanning + manual verification
**Scope**: src/aeat/**, src/aeat/locales/**, src/aeat/entrypoints/**
**Cross-Referenced Against**:
- 2026-05-19-code-duplication-sweep-research.md
- 2026-05-19-spanish-stem-terminology-authority-adr.md

**Status**: CLEAN — No residue violations detected.
