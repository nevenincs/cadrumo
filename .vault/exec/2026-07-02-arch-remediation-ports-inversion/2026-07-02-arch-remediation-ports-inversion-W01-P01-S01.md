---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:554a23ad78b6d677284d94818fc66809c37e3424c485ed26af151fdeb64ea8e1'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the usage_ratios service persistence in one atomic commit: declare the repository port in domain, move the concrete class under adapters.persistence importing substrate only from the storage package public surface, sweep consumers, update __all__, and delete the usage_ratios pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/usage_ratios/_service.py`

## Description

- Create the persistence adapter `adapters/persistence/profile/usage_ratios.py` holding the encrypted secure-object `load`, `save`, and censo refuse-load guard, importing substrate primitives only from the storage package public surface.
- Reduce `domain/usage_ratios/_service.py` to persistence-substrate-free logic: the secure-object key, the per-bucket read-modify-write lock, and the censo-derived HOME_OFFICE ratio computation; drop the moved functions from the package `__all__` and re-point its docstring.
- Sweep every consumer and test from the domain import home to the adapter home across aggregation, ledger, user_profile, cli, and the storage adapter runtime test support.
- Remove the three `usage_ratios._service` production domain-to-adapters entries from the gate ledger; add the domain and application test-fixture edges and the two narrow `_ratios`/`_preflight` production edges; ratchet the domain baseline down and the application total up, holding the application source-module count flat via narrow targets.
- Add the generated API-reference stub for the new adapter module.

## Outcome

- Landed as commit `9d4b650c9` (subject tagged `relocation:usage-ratios-service`), 21 files. The `domain.usage_ratios` package no longer imports any persistence substrate.
- Domain-to-adapters pinned entries fell from 70 to 69; the domain's persistence coupling relocated to the sanctioned application-to-adapters layer (total 330 to 336, source-module count held at 77).
- Collection clean; ruff clean; the API-reference scaffold check clears the new module; the import-linter structural ledger gate plus the usage_ratios domain suite and the ledger, aggregation, user_profile, and storage-adapter roundtrip consumers pass against real encrypted SQLite (no mocks).

## Notes

- A concurrent cross-session import-centralization campaign held roughly 240 files staged in the shared index while this step was in flight, overlapping the import blocks of `_actions_common`, `_preflight`, and `_censo_sync`. Per coordinator direction the commit was held until that campaign landed; on resume those three files already carried the correct adapter import at HEAD (their working-tree edits had been captured by the campaign's commit), leaving the adapter module they depend on and the remaining consumers to land here. HEAD was briefly incomplete between the two commits; this commit restores a whole, collectible tree.
- The two `test_source_mesh_profile_live` failures observed during the run belong to a peer's source-mesh provenance work, not this step. `lint-imports` exits non-zero on a pre-existing stale ignore unrelated to this surface, so the structural ledger gate was used as the enforcement instrument instead.
