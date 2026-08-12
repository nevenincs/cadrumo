---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
step_id: 'S32'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Enforce export verification after the write

## Scope

- `src/cadrumo/application/filing/_export.py`
- Direct real-byte filing export tests.

## Description

- Re-read the exact artefact written by `export_draft` through `verify_export`.
- Reuse the renderer's registry schema provider and require `DeclaracionVerifyVerdict.MATCH` before constructing or returning a receipt.
- Raise the registered `FilingExportError` on `MISSING` or `DRIFT`, without adding a parallel error authority.
- Keep the standalone verifier and classify an existing but unreadable path as `MISSING` rather than leaking an untyped filesystem error.
- Preserve the existing write policy: the draft writer leaves a failed artefact available for inspection, while the work-unit writer catches the typed error and removes its owned sibling `.tmp` before any export event is emitted.

## Outcome

`export_draft` now returns a receipt only after the exact file it atomically
wrote re-parses through the same registry snapshot with a `MATCH` verdict.
`MISSING` and `DRIFT` both raise the registered `FilingExportError`; no receipt
can escape that branch. The work-unit caller therefore reaches neither its
event emitter nor its final rename, and its existing typed-error handler removes
the owned sibling `.tmp`. A direct draft export retains the written artefact,
because that lower-level writer declares no deletion policy.

The load-bearing regression builds a valid production
`ExportLayoutDefinition`, not a parser imitation: an optional casilla-only
record has no literal/discriminator identity. The production renderer writes
the record; the production parser refuses its trailing bytes; and
`export_draft` itself raises instead of returning a receipt. Companion proofs
cover a supported Modelo 131 roundtrip, real on-disk casilla drift, and an
existing unreadable path classified as `MISSING`.

Focused Ruff and BasedPyright passed. Eleven focused filing-export tests passed
serially, including all four post-write-tripwire proofs. The exact
`uv run --no-sync aeat app modelo export --help` console path rendered
successfully. The existing Modelo 111 CLI integration smoke remains red before
the export surface because its profile fixture does not explicitly declare
`iva.m303_regime_composition`; this is the same unrelated profile-fixture
boundary recorded by S31, not a tripwire failure.

## Notes

No registry data, CLI surface, staging area, or peer-owned dirty path was edited.
