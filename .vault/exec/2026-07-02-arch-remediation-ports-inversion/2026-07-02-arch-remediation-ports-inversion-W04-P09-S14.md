---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:6d36aa87ee4c9f19e95cf8f7d2d0304b0192d8b6943c43cf9978f26689a46f90'
step_id: 'S14'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the modelos filing repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/modelos/_filing_repository.py`

## Description

- Move the concrete `ModeloRecordCatalogueRepository` from the domain module
  `_filing_repository.py` to the persistence adapter `modelos_filing.py`, behind
  the pre-existing `ModeloRecordCatalogueRepositoryProtocol`, adjusting the moved
  method-level storage imports to the sibling storage package.
- Slim the domain module to the pure `upsert_filing_record` helper, the
  `ModeloRecordPersistenceError`, and the namespace / schema-version constants;
  redeclare the same constants in the adapter as the persisted-envelope contract.
- Drop the concrete repository from the `domain.modelos` facade re-export and its
  `__all__`; the read-side protocol and the pure helper stay on the facade.
- Sweep every consumer import of the repository class to the adapter home with a
  multiline-aware rewriter (facade single-line, mixed, and paren-block forms),
  split the domain roundtrip test's private import, and AST-verify zero residual
  facade/private repo-class imports.
- Reconcile `.importlinter`: drop the stale `domain.modelos._filing_repository`
  storage edge, add the `modelos_filing` adapter-consumer pins discovered by
  `lint-imports`, and raise the application-to-adapters pin ratchet.
- Reconcile the lazy-import policy: drop the domain storage edge, add the adapter
  storage-deferral edge and the three application function-local adapter edges,
  and raise the two site ceilings plus the allowlist edge ceiling.
- Regenerate the adapter apidocs stub and its parent toctree.

## Outcome

Landed as one atomic pathspec commit `05ab9eb2b2` (58 files). Full `src/aeat`
`--collect-only` collects clean pre-stage. The structural gates
`test_importlinter_ledger` and `test_lazy_import_policy` pass, the layered
import contract is KEPT, apidocs `scaffold --check` reports no drift, and the
filing-record roundtrip suite passes against real encrypted SQLite. Scoped
ruff check and format are clean on the authored file set.

## Notes

- Shared-worktree hygiene: the renta M100 peer holds large uncommitted WIP
  (registry TOML plus `_ledger_bindings.py`, `_first_slice_routing.py`, locale
  catalogues) in the tree. The stage was scoped by explicit pathspec to the 58
  authored files; a name-and-content audit plus a since-session-start commit
  diff confirmed the staged set contained no peer hunks and no peer file was
  raced. A read-only `ruff check --diff` over the peer files confirmed no import
  or format drift was introduced to them.
- The read-side `ModeloRecordCatalogueRepositoryProtocol` intentionally remains
  on the domain facade; only the concrete class relocated, matching the sibling
  verification-report landing shape.
