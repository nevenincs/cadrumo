---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S33'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove repeated active-session eviction removes current and boolean ContextVar visibility after the existing key zeroization and engine disposal, preserves nested outer-session restoration, and clears an already sealed binding

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session.py`

## Description

- Ground active-session eviction and adjacent test coverage with fresh Vaultspec-RAG searches and exact symbol scans.
- Add a real-session proof that close-and-evict zeroises both key buffers, seals the session, clears both visibility observers, and repeats as a no-op.
- Prove nested inner eviction restores the exact unsealed outer binding when the inner activation token unwinds.
- Prove an already-sealed object can remain explicitly bound and is removed by active-session eviction.

## Outcome

- Landed the three-test proof in `a1f7fe2a0e`.
- Ruff passed for the touched test file.
- Twenty bucket-session and adverse-session tests passed in an isolated frozen environment.
- The uncached import graph analyzed 3,422 files and 16,160 dependencies with five contracts kept and none broken.
- Fresh-RAG formal review passed with no findings and confirmed the tests are non-tautological, nonduplicative, leak-free, and compliant with the real-behavior test policy.

## Notes

- Existing tests covered direct session close and adverse sealed reads but none invoked `close_active_bucket_session`; the new cases fill only that gap.
- The repeated call is folded into the primary eviction proof, avoiding a redundant no-active test.
- No fakes, mocks, stubs, patches, monkeypatching, skipped tests, expected failures, business-logic mirrors, data loss, or runtime scaffolds were introduced.
- The shared damaged `.venv` remained untouched; every Python-backed command used an isolated frozen environment.
