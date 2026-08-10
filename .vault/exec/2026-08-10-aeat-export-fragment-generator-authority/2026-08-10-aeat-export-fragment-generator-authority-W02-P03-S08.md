---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:cec68d6c6b44c1454f9978e06c21056518a7c4f3513509dadc137a2833ca2f5c'
step_id: 'S08'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Render the complete target export tree with stable partitioning and canonical TOML serialization

## Scope

- `dev/registry/`

## Description

- Extend the joined record design with exact parser-sheet and semantic-record authority.
- Require explicit source-hash-pinned transport policy and render a fresh complete `export/` tree with stable zero-padded fragments.
- Derive schema wire values from official IR type, validation, and content; reject unsupported or ambiguous forms.
- Enforce an explicit declared total and contiguous physical field geometry before any fragment is written.
- Prove deterministic bytes and production loader compatibility through real filesystem tests.
- Block historic-output lookup, copying, fuzzy admission, and fallback terms with a structural regression guard.

## Outcome

The renderer produces only a fresh, complete target tree from `JoinedRecordDesign` and `ExportRenderProfile`. It emits canonical TOML metadata plus one deterministic record fragment per official record, while retaining derivation codes for the later provenance step.

The independent review initially found missing-total and incomplete-geometry failures. Both now reject before writing; re-review passed after direct tests for missing total, invalid first offset, gap, overlap, and terminal mismatch.

## Notes

`pytest dev/registry/tests -q` completed with 63 passing tests. Scoped Ruff format and lint checks passed, and scoped BasedPyright reported zero errors, warnings, and notes.

Numeric forms without explicit normalizable official content intentionally remain refused. No legacy registry tree is read, copied, derived, or accepted as a fallback authority.
