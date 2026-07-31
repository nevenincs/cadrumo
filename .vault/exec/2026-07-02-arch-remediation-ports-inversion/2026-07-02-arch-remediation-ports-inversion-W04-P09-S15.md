---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:b863f71688547f716071e270b770225fa64c98e2cdb269d47f293e98159d275c'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the modelos calculation repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/modelos/_calculation_repository.py`

## Description

- Move the concrete `CalculationRevisionCatalogueRepository` from the domain
  module `_calculation_repository.py` to the persistence adapter
  `modelos_calculation.py`, behind the pre-existing
  `CalculationRevisionCatalogueRepositoryProtocol`, adjusting the moved
  method-level storage imports to the sibling storage package.
- Slim the domain module to the pure `upsert_calculation_revision` helper, the
  `CalculationRevisionPersistenceError`, and the namespace / schema-version
  constants; redeclare the same constants in the adapter as the persisted-envelope
  contract to avoid orphaning stored envelopes.
- Sweep every consumer import of the repository class to the adapter home;
  grep-verify zero residual concrete imports of the old path across absolute,
  intra-domain relative, and deferred / function-local forms. The read-side
  protocol and the pure helper stay on the domain facade.
- Move the two dedicated repository roundtrip tests (`test_calculation_repository_roundtrip`
  and `test_ledger_filing_evidence_roundtrip`) to the adapter tests folder; the
  system under test is now the adapter, so retag `hex_domain` to
  `hex_persistence_adapter` and retarget their relative imports, matching the
  prior nine domains' precedent.
- Reconcile `.importlinter`: drop the stale `domain.modelos._calculation_repository`
  storage edge and the two moved-test edges, add the 92 application / domain
  adapter-consumer pins discovered by `lint-imports`, and raise the
  application-to-adapters pin ratchet from 656 to 747.
- Reconcile the lazy-import policy: move the deferred storage edge from
  `PORTS_INVERSION_PENDING` to `ADAPTER_INTERNAL_DEFERRAL`, add the three
  application function-local adapter deferrals, and raise
  `ADAPTER_INTERNAL_DEFERRAL` 159 to 162, `APPLICATION_DEFERRAL` 496 to 500, and
  the allowlist edge ceiling 485 to 488.
- Re-point the calc entry in `test_repository_sensitivity_class` to the adapter
  path, and add the adapter apidocs stub plus its parent toctree entry.

## Outcome

Landed as one atomic verified-index commit `de45da44d6` (121 files). The full
`src/aeat` `--collect-only` collects clean (11889 tests, zero import errors). The
structural gates `test_importlinter_ledger`, `test_repository_sensitivity_class`,
`test_runtime_repository_enrollment`, and `test_hardening_convention_guards` pass;
`test_docstring_core_struct_links` passes; the layered import contract has zero
calc-related violations; apidocs `scaffold --check` reports zero calc drift; and
the calculation-revision roundtrip plus ledger-evidence roundtrip suites pass
against real encrypted SQLite. Scoped `ruff check` and `format` are clean on the
authored file set.

## Notes

- Shared-worktree hygiene: four peer campaigns held uncommitted or
  freshly-committed WIP in the tree (renta M100 registry, LLM run-telemetry,
  rectificativa amendment, bucket-maintenance sandbox). The stage was scoped to
  the 121 authored calc-relocation files; a name-and-content audit confirmed zero
  peer files and zero foreign hunks in the staged index.
- The application module `_amendment_actions.py` carried the peer rectificativa
  amendment wiring as uncommitted working-tree WIP interleaved with this
  relocation's calc import retarget. The calc import change was staged in
  isolation via `git apply --cached` of a HEAD-anchored two-hunk patch, leaving
  the peer amendment lines intact in the working tree; the commit was then taken
  as a verified index rather than a pathspec commit (a pathspec commit would have
  re-staged the peer's interleaved lines).
- The read-side `CalculationRevisionCatalogueRepositoryProtocol` intentionally
  remains on the domain facade; only the concrete class relocated. The domain
  module is trimmed but not deleted (it retains the pure helper, the boundary
  error, and the persisted-envelope constants).
- Residual reds at commit HEAD are exclusively peer-owned and pre-existed this
  commit: the layered contract, lazy-import policy, and apidocs `scaffold --check`
  each carry non-calc violations from the LLM run-telemetry (#407), amendment
  (#234), and bucket-maintenance-sandbox campaigns. None involve
  `modelos_calculation`.
