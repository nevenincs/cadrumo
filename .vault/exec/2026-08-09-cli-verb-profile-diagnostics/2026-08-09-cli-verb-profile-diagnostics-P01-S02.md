---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:80e9c540eb2d01e2e6a5eba2105ebb538f4a9a18f8a5d9c7943e63c97028c833'
step_id: 'S02'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Promote the selector-to-path resolver to the owning package public facade

## Scope

- `src/cadrumo/domain/user_profile/__init__.py`

## Description

- Checked whether the resolver needed its own facade entry, given it was implemented as a method on `ProfileSchemaDefinition` rather than as a module-level function.
- Confirmed `ProfileSchemaDefinition` is already imported and listed in the package's `__all__`, so consumers in the application and entrypoint layers reach the resolver through the existing public export with no private-module import.

## Outcome

**Satisfied by construction, no code changed.** The Step's requirement is that cross-package consumers reach the resolver through the owning package's public facade, and they already do: the resolver is a method on an exported class.

Recording this rather than adding a redundant module-level wrapper is the substantive choice. A wrapper would have created a second way to ask the same question, which is the fragmentation this package's import rules exist to prevent, and it would have had exactly one caller shape that the method already serves.

## Verification

No code change to verify. The export was confirmed by reading the package facade: `ProfileSchemaDefinition` appears both in the import block and in `__all__`. Consumers added in later Steps import it from the package root, and the import-hygiene gate that forbids cross-package private-module imports covers those call sites.

## Notes

The Step row was written before the implementation shape was settled, and anticipated a free function. The shape chosen in the sibling Step made the promotion a no-op. Flagged here rather than silently closing the row, since a closed row with no diff is otherwise indistinguishable from work that was skipped.
