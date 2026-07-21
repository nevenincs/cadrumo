---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S13'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the modelos repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/modelos/_repository.py`

## Description

- Verify at HEAD that the work-unit catalogue repository is already ports-compliant (concrete relocated by a prior pass in this campaign).
- Confirm the domain module holds only pure logic: `WorkUnit`/`WorkUnitCatalogue` models plus the `upsert_work_unit`/`remove_work_unit` mutators, with an AST scan finding zero `adapters` imports (top-level, function-local, or `TYPE_CHECKING`).
- Confirm the concrete `WorkUnitCatalogueRepository` lives under `adapters.persistence.profile.modelos_work_units`, importing domain types via the `domain.modelos` public facade and storage via the public `..storage` surface.
- Confirm the domain-facing port `WorkUnitCatalogueRepositoryProtocol` is declared in `_protocols.py` and exported.
- Confirm zero production `domain.modelos -> adapters` pinned edges remain in the ledger and the work-unit roundtrip suite passes.

## Outcome

Ports-compliant at HEAD. The concrete relocated in `8f9cb8772c` with a follow-up facade-routing pass `35848156c7`; no production `domain.modelos -> adapters` edge remains. Roundtrip `test_work_unit.py` green (part of a 45-test modelos run). Independent read-only verification (agent, this session) quoted the import lines and grep output as evidence.

## Notes

The concrete-relocation commit `8f9cb8772c` was NOT tagged `relocation:work-unit-repository` per the atomic-relocation-commit convention (unlike the S15/S16/S17 siblings). The structural work is complete and verified; only the commit-subject tagging discipline was missed on that earlier commit. Recorded honestly rather than re-tagging history.
