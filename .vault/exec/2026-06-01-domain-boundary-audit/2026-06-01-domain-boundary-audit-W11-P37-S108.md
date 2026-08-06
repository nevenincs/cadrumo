---
tags:
  - '#exec'
  - '#domain-boundary-audit'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:0f71bce614a811cd7a619d9ae2bfe577f7a37efa1e599179c19a618600c12e12'
step_id: 'S108'
related:
  - "[[2026-06-01-domain-boundary-audit-plan]]"
---

# Prune/update the stale .importlinter ignore entries that W11's repoint left unmatched: the domain repo edges now target the top-level package, so entries naming aeat.adapters.persistence.storage.envelope / .sql / .envelope._envelope for filing/justificante/submission/buckets/transactions/invoices _repository are unmatched (the 15->22 unmatched-ignore warning bump). Update each to the current '-> aeat.adapters.persistence.storage' edge (or delete if the new edge is deferred/unflagged)

## Scope

- `verify lint-imports warning count drops with no new violation. Delicate shared-file edit — verify per-edge and avoid peer-WIP collision`
- `.importlinter`

## Description

- Grounded the investigation with a RAG code sweep, then read the W11 repoint commit `4eb5004070` (S104-S106): it repointed the 15 domain repositories plus the double-private `envelope._envelope` reach-in in `domain/transactions/_repository` from the private `storage.sql` / `storage.envelope` submodules to the top-level `aeat.adapters.persistence.storage` package, but touched only source files, not `.importlinter`.
- Established that the stale ignore entries S108 was filed to prune were already reconciled by the interleaving arch-remediation-ports-inversion campaign (commits `be5ca85b22` declaring the domain-not-adapters contract exhaustively with the zero-production gate, plus the per-repository relocation commits `48398f93d1`, `8b89314733`, `b941aefe87`, `d1ca224705`, `c60d45b404`, `05ab9eb2b2`, `5d1018a425`, `de45da44d6`, `8175c98e9a`, `3476219f28`, `dde6f92d1d`, `a43d1b0054`), which moved every concrete repository under `adapters.persistence.profile` and rewrote the ignore ledger to match.
- Verified the current on-disk state directly: `grep` finds zero `storage.envelope` references in `.importlinter` and the only non-test `storage.sql` ignore entry is `aeat.application.review.conftest`, not a domain `_repository`.
- Read the import-linter internals to interpret the gate correctly: every contract sets `unmatched_ignore_imports_alerting = error`, and `contract_utils._handle_unresolved_import_expressions` RAISES `MissingImport` on any unmatched ignore rather than emitting a soft warning; `layers.check` computes that removal first, before illegal-dependency analysis.
- Ran `uv run --no-sync lint-imports` as the real gate and captured full output to disk.
- Ran the governing structural gate `test_importlinter_ledger.py` to distinguish owner on the residual red.

## Outcome

- No `.importlinter` edit was required or made: the stale storage-repo ignore entries are already gone. The delicate shared file was left untouched (`git diff -- .importlinter` clean throughout).
- `lint-imports` evidence: `4 kept, 1 broken`, exit 1, with NO `(N warnings)` annotation on any contract line and NO `No matches for ignored import` / `MissingImport` output. Because unmatched ignores under `error` alerting would raise `MissingImport` before illegal-dependency computation, a clean per-contract `KEPT`/`BROKEN` result proves the unmatched-ignore count is zero across all five contracts. The 15->22 unmatched bump S108 described has been driven to 0.
- The single broken contract (`AEAT layered architecture`) is broken SOLELY by real `#407` illegal dependencies — new `aeat.application.*.tests.* -> aeat.adapters.*` edges not covered by the ignore ledger — not by any stale storage entry.
- `test_importlinter_ledger.py`: 3 passed, 1 failed. The failure is exactly the pre-flagged `#407` peer issue `test_application_to_adapters_pin_count_does_not_grow` (`assert 845 <= 840`), handed off separately and left in place per the brief. The three passing tests include `test_ignore_import_modules_resolve_on_disk` (every ignore source and target resolves on disk) and `test_zero_production_domain_to_adapters_edges` (no production domain to adapters ignore edge), which are the structural gates for S108's concern.

## Notes

- Owner triage per `full-tree-gate-must-distinguish-owner`: the only residual `.importlinter`-adjacent red is `#407`'s application-to-adapters pin-count growth (845 vs baseline 840). It is a separate peer campaign's surface, explicitly out of scope for S108, and was NOT touched; its baseline was NOT bumped.
- Disposition: S108 is complete by subsumption. The remediation it specified (repoint stale `storage.sql` / `storage.envelope` / `storage.envelope._envelope` repo edges to the top-level package, or delete) was performed by the ports-inversion campaign as part of relocating the repositories to `adapters.persistence.profile`. Verifying the unmatched-ignore count is 0 with no new violation satisfies the step's verification gate without a redundant hand-edit that would only risk churn on a heavily shared file.
