---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:bbf4cc13d7c1c3ac5078ad8febf78dedda343736dc45b77e8e536458116cd7ad'
step_id: 'S34'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove same-object file-provider eviction closes real bucket-routed storage, clears provider and active-session bookkeeping, and permits a clean fresh reopen with the persisted bucket DEK and distinct session and engine handles

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`

## Description

- Ground provider teardown, file custody, wrapped bucket-DEK recovery, session ownership, and engine disposal with fresh Vaultspec-RAG searches and exact symbol scans.
- Replace the initial test-only provider design with one same-object `FileFallbackMasterKeyProvider` lifecycle proof over a registered `BUCKET_DEK_V1` bucket.
- Provision the encrypted file master key and wrapped bucket DEK through production APIs, then acquire and query the real bucket-routed SQLite engine.
- Verify each provider exit clears active visibility and provider bookkeeping, seals the captured session, and permits a distinct session and engine to reopen with the persisted DEK.
- Resolve the passphrase through validated settings rather than an injected callback seam.

## Outcome

- Landed the production file-provider lifecycle proof in concurrent commit `c77738fee1` and the configured-passphrase correction in `741d59cbba`, after plan reconciliation in `a2252c9e61`.
- Ruff passed for the touched test file.
- Twenty-one file-provider and engine-lifecycle tests passed in an isolated frozen environment.
- The uncached import graph analyzed 3,425 files and 16,179 dependencies with five contracts kept and none broken.
- Fresh-RAG formal review passed with no findings and confirmed real persisted custody, bucket routing, same-object reentry, distinct session and engine identity, exact cleanup, and test-policy compliance.

## Notes

- Existing engine tests already owned pool replacement and profile-switch behavior; S34 composes those lower-level guarantees with the production file provider and does not repeat their assertions.
- The first design used the exported ephemeral provider and a real explicit-URL SQLite engine. A Terra overlap audit correctly identified that it did not exercise persisted file custody or the bucket-routed backend, so it was replaced before closure.
- A concurrent shared-worktree commit captured the initial production test while the supervisor was validating it. The supervisor preserved that commit and landed only the credential-source correction as a narrow follow-up.
- No fakes, mocks, stubs, patches, monkeypatching, skipped tests, expected failures, business-logic mirrors, data loss, or runtime scaffolds were introduced.
- The shared damaged `.venv` remained untouched; every Python-backed command used an isolated frozen environment.
