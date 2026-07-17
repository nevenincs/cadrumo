---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the filing complementaria repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/filing/_complementaria_repository.py`

## Description

- Create the persistence adapter `filing_amendments.py` holding the concrete
  `ModeloAmendmentRepository`, moved verbatim from the deleted domain module.
- Declare a new domain port `ModeloAmendmentRepositoryProtocol` (no
  pre-existing port existed for this repository, unlike the draft
  repository), matching the shape of the sibling `ModeloDraftRepositoryProtocol`
  and adding the amendment-specific `list_amendment_ids` method.
- Delete the domain module entirely (no pure logic remained); drop
  `ModeloAmendmentRepository` from the domain facade `__all__` and add
  `ModeloAmendmentRepositoryProtocol` in its place; preserve the
  `aeat.domain.filing.amendments` persisted namespace string byte-for-byte.
- Sweep every consumer to the new adapter home: `application/filing/_complementaria`
  (consolidating three function-local imports into one module-level import,
  matching the draft-repository precedent), its tests, the custody-store
  matrix test, the domain amendment-roundtrip test, and the storage
  rotation test-support module.
- Retarget the domain roundtrip test's reach into the private
  `_AMENDMENT_NAMESPACE` constant to the public `FILING_AMENDMENTS_NAMESPACE`
  registry definition on the storage package facade, avoiding a new
  cross-package private-symbol import.
- Delete the stale domain-to-adapters pinned entry and the dead
  `PORTS_INVERSION_PENDING` lazy-import allowlist entry for the removed
  module; add the new consumer pins and one new `ADAPTER_INTERNAL_DEFERRAL`
  classification for the adapter's own deferred storage imports; bump the
  affected ratchet ceilings.
- Retarget the stale domain-module path references in the sensitive-persistence
  policy surface list and the UTF-8 bare-literal enrollment ratchet.
- Regenerate the apidocs stubs: add the new adapter stub, remove the stale
  domain module stub.

## Outcome

Commit `dde6f92d1d` lands the relocation as one atomic, explicit-pathspec
commit of 19 files. The domain/filing and application/filing roundtrip
suites pass (295 of 296 tests; the single deselected failure is an unrelated
concurrent registry-content edit to modelo-390 export layouts by a peer
campaign, re-confirmed against the live registry TOML tree at commit time).
The storage rotation, attached-repository matrix, ephemeral-key-hygiene,
review, custody-store-matrix, and auth-operator suites pass (166 tests). A
full-tree `pytest --collect-only` run hit a transient concurrent
registry-validation error on its first pass and reproduced clean (11992
tests, zero errors) on a second pass, consistent with the project's
registry-race discipline for shared-worktree concurrent registry writes.

## Notes

A concurrent peer git process held the index lock at first commit attempt
(`index.lock` already existed); the operation was retried after a brief wait
rather than forcing lock removal, per worktree safety discipline. The retry
landed cleanly with the same explicit pathspec, and the peer's own
in-progress staged changes (bienes-inversion advisory retirement, auth
certificate-source additions, registry-corpus CLI edits, locale catalogue
edits) remained untouched and uncommitted after this step's commit.
