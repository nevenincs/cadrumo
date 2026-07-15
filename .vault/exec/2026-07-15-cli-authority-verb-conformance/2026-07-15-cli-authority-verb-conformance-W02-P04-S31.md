---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S31'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Introduce one public idempotent active-session eviction boundary that closes the currently bound BucketSession before clearing ContextVar visibility, route idle-expiry and interpreter-exit cleanup through it, and re-export it through the master-key and storage facades

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_active_session.py`
- `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`
- `src/cadrumo/adapters/persistence/storage/__init__.py`

## Description

- Ground the session, provider, engine, idle-expiry, and logout call graphs with fresh Vaultspec-RAG searches and exact symbol scans.
- Identify the already-complete `BucketSession.close` authority and remove duplicate class-close work from S31 and S33.
- Add `close_active_bucket_session` as the sole active-context eviction boundary while delegating zeroisation, sealing, and engine disposal to `BucketSession.close`.
- Clear only the captured current binding in a `finally` block so cleanup failures cannot advertise a stale session and reentrant replacement bindings survive.
- Route idle expiry and interpreter-exit cleanup through the same close-and-evict boundary.
- Re-export the operation through the master-key and top-level storage facades for later strong-logout composition.

## Outcome

- Landed the implementation in `0db660fa6c` after duplicate-work plan reconciliation in `4f40d0e8ae`.
- Ruff passed for all three touched production files.
- Seventeen existing bucket-session and adverse-session tests passed in an isolated frozen environment.
- The uncached import graph analyzed 3,422 files and 16,158 dependencies with five contracts kept and none broken.
- Fresh-RAG formal review passed with no findings and confirmed correct nested `ContextVar`, exception, idle-expiry, atexit, facade, and authority semantics.
- No second key-zeroisation, session-sealing, engine-disposal, or provider-eviction implementation was introduced.

## Notes

- The initial S31 wording duplicated behavior present since earlier custody work. S31 now owns only active binding eviction; S32 owns provider bookkeeping and S33 owns the new visibility proof.
- `close_active_bucket_session` is safe when no session is active and when an already sealed session remains bound. Nested activation restoration remains owned by the existing context-manager tokens.
- The delegated implementation lane completed semantic and documentation grounding but did not edit before it was stopped; the supervisor applied the reviewed scope directly.
- The shared damaged `.venv` remained untouched; every Python-backed command used an isolated frozen environment.
- No data loss, skipped tests, persistent failures, or runtime scaffolds remain.
