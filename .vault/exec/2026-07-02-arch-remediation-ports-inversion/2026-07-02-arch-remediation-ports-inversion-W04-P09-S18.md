---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S18'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the modelos participation index behind a port in one atomic commit after verifying its pinned edge inventory at execution time, preserving the derived-and-rebuildable invariant

## Scope

- `src/aeat/domain/modelos/_participation_index.py`

## Description

- Verify the participation-index concrete already relocated to `adapters.persistence.profile.participation_index` (peer commit `7b12dc8261`), importing domain symbols via the `domain.modelos` public facade and storage via the public `..storage` surface, with the derived-and-rebuildable invariant preserved.
- Declare the missing domain-facing port: add `TransactionParticipationIndexRepositoryProtocol` to `domain.modelos._protocols` and export it via the package facade, so the index sits behind a port like its sibling catalogue repositories (S13/S16 already had theirs).
- Model the port on the concrete's per-transaction surface (`bucket_id`, `exists(transaction_id)`, `load(transaction_id)`, `save(index)`) — the index is keyed by transaction, not a singleton catalogue.
- Confirm the concrete structurally conforms to the runtime-checkable Protocol and the participation roundtrip + anti-tautology suite passes.

## Outcome

Complete. Port added in commit `7138bc2a9b`; the concrete `TransactionParticipationIndexRepository` structurally conforms (verified `bucket_id`/`exists`/`load`/`save` present, `runtime_checkable`). `test_participation_index_roundtrip.py` green (4 passed; anti-tautology on-disk-mutation proof present). No production `domain.modelos -> adapters` edge; the derived-cache invariant (`ledger-participation-index-is-derived-rebuildable`) is documented on the port. Clean collection at 11993 tests; apidocs `scaffold --check` clean.

## Notes

INCIDENT (coordinator, this session): the port commit `7138bc2a9b` was created with a `git commit` that carried NO pathspec while a peer's fully-staged `bienes_inversion`-advisory-removal change (15 files) sat in the shared index — so those 15 peer files were swept into this commit under the S18 message (the `subagent-commits-require-explicit-pathspec` failure mode). Assessed immediately: HEAD is COHERENT (git-grep confirms zero dangling references to the deleted `_bienes_inversion_advisory` module), NO data loss (the peer's live worktree work remained intact as unstaged/untracked entries and had moved past the committed snapshot), and nothing was pushed. A `git revert` was deliberately NOT performed: it would clobber the peer's newer worktree edits, violating the peer-WIP-preservation discipline. The two S18 port files are legitimately in the commit; the bundling is recorded here transparently. All subsequent commits used explicit pathspecs verified via `git diff --cached` before commit.
