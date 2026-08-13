---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:37f9e8650688cca654fe355c276eb9bffe33f803eccc4f8ac98f56ecf94c8aea'
step_id: 'S04'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Terra XHigh implement password and optional recovery envelopes, strict external recovery artifacts, DEK sentinel proof, and immutable capsule publication

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Added strict canonical password and optional recovery envelope records with distinct authenticated-data domains, immutable `dek_epoch`, bounded parsers, and production supervised wrapping and unwrapping through the S03 worker boundary.
- Added authenticated recovery-artifact export that revalidates the current password and sentinel, creates the named destination exclusively, returns structured security warnings, and imports only canonical UUID- and epoch-matched artifacts.
- Added immutable DEK sentinel creation and verification, plus committed capsule publication with a minimal canonical commit marker built and durably staged before the sole sibling-directory publication operation.
- Enforced current-marker-only recognition and normal password material loading without resolving the optional recovery path.
- Hardened hostile-filesystem handling with descriptor-relative no-follow POSIX traversal and native Windows no-reparse identity handles for capsule publication, recovery-artifact export, and recovery-artifact import.
- Added real filesystem and cryptographic tests for recovery and password unwrap equivalence, artifact warnings and collision refusal, import bounds and link refusal, committed-marker isolation, external recovery access isolation through actual password unlock, staging crash recognition, no-replace publication collision, and symlink/reparse refusal.

## Outcome

`W01.P02.S04` now supplies the current-format custody envelope, independent optional recovery, sentinel proof, canonical external artifact, and immutable capsule-publication substrate. Password login reads only the committed marker, password envelope, and sentinel; it performs no recovery-path stat, open, or read. Recovery export requires current-password authentication and sentinel proof; import is bounded, canonical, no-follow, and identity-scoped. Publication creates a fully durable sibling stage and recognizes only a matching committed marker after the one no-replace publication boundary.

Focused verification completed on Windows:

- `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py -q` - 9 passed in 27.86 seconds.
- `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/custody` - clean.
- `uv run --no-sync ty check src/cadrumo/adapters/persistence/storage/custody` - clean.
- `uv run --no-sync basedpyright src/cadrumo/adapters/persistence/storage/custody` - 0 errors, 0 warnings.

Independent Sol review re-ran the focused suite with 9 passing tests in 31.38 seconds and re-ran Ruff, ty, and basedpyright clean. It found no unresolved critical or high finding.

## Notes

The initial review found publication, export-authority, enrollment, and evidence gaps. Final re-review additionally found recovery-import reparse exposure and incomplete independent isolation proof. All findings were remediated and independently re-reviewed before this record was written. The stage-marker crash test proves a marker written only under the hidden sibling stage is undiscoverable and normal loading refuses it. No product storage, remote state, service state, Git state, or later plan Step was changed.
