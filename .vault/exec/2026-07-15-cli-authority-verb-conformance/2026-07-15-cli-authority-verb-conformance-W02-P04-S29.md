---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:9d4d9b145bbed05e3dc3ecdad09013630b67169244847bdff69222d56a79fbc2'
step_id: 'S29'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove byte-exact failed-create rollback through the repository transaction nested under outer pointer ownership, then prove dangling-pointer repair fails closed under real thread contention and succeeds after lock release against real files

## Scope

- `src/cadrumo/application/user_profile/tests/test_orchestration_pointer.py`

## Description

- Seed a real survivor and a real victim custody route through production profile storage spans.
- Invoke `ProfileRepository.create` with schema-invalid facts while it is nested under outer `active_profile_pointer_transaction` ownership and a real victim session.
- Assert byte-exact restoration of a parseable noncanonical survivor pointer both before and after the outer transaction releases.
- Assert the rejected victim leaves no manifest or bucket directory and the survivor remains loadable.
- Hold the public pointer transaction in a worker thread with bounded event handshakes.
- Prove a contended dangling-pointer repair raises `LockAcquisitionError` without changing pointer bytes, then succeeds after lock release.
- Ground implementation and review with fresh Vaultspec-RAG searches and exact symbol scans.

## Outcome

- Landed the test-only implementation in `e28ef84feb`; no production file was changed.
- The focused orchestration-pointer module passed five tests in an isolated frozen environment.
- Four adjacent rollback, repair, and cross-process lock tests passed in an isolated frozen environment.
- Ruff and diff checks passed.
- An uncached isolated import graph analyzed 3,422 files and 16,152 dependencies with five contracts kept and none broken.
- Pre-edit, post-edit, and formal-review semantic searches found one production pointer authority and no duplicate test coverage.
- Formal review passed with no blocker, high, medium, or low findings.

## Notes

- One accidental non-isolated RAG invocation attempted dependency reconciliation and partially removed installed `cryptography` files from the shared `.venv` before Windows denied replacement of a loaded binary. No repair was attempted while peer processes held the environment; every attributable gate then used an isolated frozen environment.
- The first short isolated import-linter probe yielded no result; the subsequent properly budgeted run passed and is the only import-graph result claimed.
- Peer changes to the pointer error superclass, repository rollback-helper extraction, and facade comment remained untouched and excluded.
- S30 retains lifecycle-repository active-profile resolution coverage; S29 added no duplicate production authority or generic lock test.
- No data loss occurred and no runtime scaffolds were left in source.
