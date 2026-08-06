---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:ba3e827559004462657bda8d2e1e471c99f1ee1a6a55ef6b1ccc7bea4d1b07d3'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the buckets event repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/buckets/_event_repository.py`

## Description

- Relocate the concrete `BucketEventHistoryRepository` from `src/aeat/domain/buckets/_event_repository.py` to the persistence adapter `src/aeat/adapters/persistence/profile/buckets.py`, behind the pre-existing `BucketEventHistoryRepositoryProtocol` which stays on the domain facade.
- Trim the domain `_event_repository.py` to keep only the pure boundary error `BucketEventHistoryPersistenceError` and the pure helper `append_bucket_event`; redeclare the namespace/version constants in the adapter as the persisted-envelope contract (strings preserved to avoid orphaning envelopes).
- Drop `BucketEventHistoryRepository` from the `domain.buckets` facade `__all__`; update the facade and `iva_compensation` docstring cross-references to the adapter class and the protocol.
- AST-sweep 118 consumer files, splitting the moved symbol out to the adapter home while sibling buckets symbols stay on the domain facade; verify zero residual old-path imports in every form (absolute facade, relative facade, relative `_event_repository`, paren-wrapped, deferred/function-local).
- Move the encrypted-SQLite roundtrip test to the adapter tests folder (marker `hex_domain` to `hex_persistence_adapter`); the catalogue-only domain test stays in domain.
- Update `.importlinter` (drop stale prod/test edges, add 99 application + 1 domain adapter-consumer pins, bump ratchet 557 to 656), `test_lazy_import_policy` (move the deferred storage edge to the adapter class, add 5 deferred application-to-adapter edges, raise the ADAPTER_INTERNAL_DEFERRAL, APPLICATION_DEFERRAL, and allowlist-edge ceilings), and `test_docstring_core_struct_links` (drop the inverted-repo anchor).
- Regenerate the apidocs stub tree (adapter stub added; domain stub retained since the module still exists).

## Outcome

Landed as one atomic commit `b941aefe87` (132 files). Full tree collects clean (11839 collected, 0 errors); layered import-linter contract KEPT; `test_importlinter_ledger`, `test_lazy_import_policy`, apidocs `scaffold --check`, and `test_docstring_core_struct_links` all green; the bucket-event-history roundtrip plus a cross-layer sample of swept consumer suites pass against real encrypted SQLite.

## Notes

- Absorbed two pre-existing red entries in `test_repository_sensitivity_class.py` (`ModeloRecordCatalogueRepository`, `VerificationReportCatalogueRepository`) whose concrete repositories landed in adapters via prior peer relocations (`05ab9eb2b2`, `5d1018a425`) but whose source paths were left pointing at emptied domain shells. Proven red at HEAD independent of this change; the test file was already in this commit's pathspec, so the stale paths were corrected in-passing and flagged for the verifier.
- Four files that appeared dirty mid-session (`adapters/outbound/llm/_run_telemetry.py`, `adapters/persistence/storage/__init__.py`, `core/_amendment_kind_regime.py`, `core/observability/_fingerprint.py`) are live peer WIP carrying no buckets content; excluded from staging and left untouched. Peer renta M100 registry WIP also untouched and out of this commit.
