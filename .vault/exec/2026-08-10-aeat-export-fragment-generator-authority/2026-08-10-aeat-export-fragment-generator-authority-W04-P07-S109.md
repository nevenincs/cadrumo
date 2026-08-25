---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5834d7c30c806d868f930c58a648fd46070b212d6dc191f6b5585f227dd2bb8f'
step_id: 'S109'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Reconcile every bundled record-design artifact through one source catalogue

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`
- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Join every bundled design to official manifest provenance without filename inference.
- Migrate six existing source rows from local LibreOffice conversions to the native AEAT binaries.
- Register fourteen additional manifest-backed official artifacts with exact path, hash, byte count, and URL evidence.
- Remove twenty-five provenance-proven local conversion copies, including six duplicate manifest rows and nineteen unmanifested extras.
- Preserve twelve sources as explicitly resolver-unselectable where official evidence does not establish non-conflicting temporal windows.

## Outcome

Commit `8406d7f45e` leaves 192 physical binary designs, all registered through the canonical source catalogue. Manifest and root counts agree at 223 artifacts. Clean detached-worktree verification passed four strict registration, manifest, source, and epoch gates; five parser-read gates; and the canonical corpus synchronizer over 61 required official URLs and 58 manifests. Ruff and formatting checks are clean.

## Notes

The twenty-five deleted conversion copies are recoverable from Git history. No allowlist baseline, inferred temporal scope, filename-derived ownership, or duplicate source authority was introduced. Twelve historically ambiguous sources remain refused with explicit reasons pending authoritative temporal evidence.
