---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:6850e99f58a4daa83e2252d35bb757bbb64c969a345db44700b00c5c15b2e46e'
step_id: 'S10'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the filing repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/filing/_repository.py`

## Description

- Create the persistence adapter `filing_drafts.py` holding the concrete
  `ModeloDraftRepository`, moved verbatim from the deleted domain module,
  behind the pre-existing `ModeloDraftRepositoryProtocol` port; preserve the
  `aeat.domain.filing.drafts` persisted namespace string byte-for-byte.
- Delete the domain module entirely (no pure logic remained); drop
  `ModeloDraftRepository` from the domain facade `__all__` and add
  `ModeloDraftRepositoryProtocol` in its place.
- Sweep every consumer to the new adapter home: `application/filing/_complementaria`,
  `application/review/_adapters`, `application/state_projection`,
  `application/user_profile/_custody_carry`, `entrypoints/cli/_common`, plus
  their tests and the storage rotation / attached-repository test support
  module (11 application and domain-test consumer sites).
- Import the bucket/runtime helpers (`resolve_filing_repository_bucket_id`,
  `secure_objects_for_filing_bucket`) from the still-domain-resident runtime
  module as a deliberate interim state mirroring the modelos ports-inversion
  precedent; the sibling runtime-relocation step closes this edge and fixes
  up the import in the same later commit.
- Delete the stale domain-to-adapters pinned entry from the import-linter
  ledger; add 11 new application/domain-test consumer pins for the adapter;
  bump the application-to-adapters and domain-to-adapters ratchet ceilings.
- Add two `APPLICATION_DEFERRAL` allowlist entries to the lazy-import policy
  gate for the two function-local adapter imports introduced in application
  code; raise the class ceiling and the total allowlist edge ceiling.
- Regenerate the apidocs stubs: add the new adapter stub, remove the stale
  domain module stub.

## Outcome

Commit `3476219f28` lands the relocation as one atomic, explicit-pathspec
commit of 26 files. The domain/filing and application/filing roundtrip
suites plus the storage rotation and attached-repository test matrix pass
(311 tests), and the broader consumer sweep (rotation, ephemeral-key-hygiene,
review, custody-store-matrix, auth operator, state-projection, overview
verbs) passes (144 tests). A full-tree `pytest --collect-only` run collects
11974 tests with zero errors. The import-hygiene scan reports exactly one
Family-1 non-test cross-package private import after this step: the
deliberate interim edge from the new adapter into the domain-resident
runtime-repository module, matching the precedent set by the modelos
filing/calculation/verification repositories during their own ports-inversion
steps. That edge is closed by the sibling runtime-repository relocation step.

## Notes

The shared worktree held unrelated peer WIP already staged in the index at
commit time (a bienes-inversion advisory retirement, a registry-corpus CLI
change, and locale catalogue edits). The commit was scoped with an explicit
pathspec naming only the 26 files this step touched; `git status` after the
commit confirms the peer's staged files remain untouched and uncommitted.
