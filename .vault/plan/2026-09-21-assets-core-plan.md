---
tags:
  - '#plan'
  - '#assets-core'
date: '2026-09-21'
tier: L2
related:
  - '[[2026-08-23-amortization-casilla-mapping-adr]]'
  - '[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-21-assets-core-cost-basis-stages-adr]]'
modified: '2026-09-21'
body_schema: body-v2
body_hash: 'sha256:cd9315d08a7326bdef0f6f1e95b91ef1a7023ebf5b999d5887f01e4a866290cd'
---

# `assets-core` plan

Deliver the complete 2025 IRPF activity-asset amortization lane through shared CLI and TUI operations and filing integration.

## Description

Approved 2026-09-21 by the user's explicit assets-core implementation dispatch.

Implement ASSETS-01 revision 0.1 under session-policy revision 1.5 and
ACCEPTANCE-01 revision 1.3. Provider is OpenAI and the lead model is GPT-5;
cc number and session UUID remain pending user provision. The accepted
amortization-casilla decision governs exclusive, atomic 2025 activity-asset
authority and the accepted IVA bienes-inversion decision preserves the separate
VAT register and reciprocal acquisition linkage. P01.S01 must settle the four
uncovered costly contracts before dependent Steps execute: IRPF asset identity,
recorded-history revisions, Modelo 130 ownership, and mixed-use-home allocation.

This session owns the new defining IRPF asset modules, asset authority
declarations, application operations, persistence adapter, resolver, owning
tests, CLI projection, TUI projection, and asset acceptance scenarios. Existing
dirty shared storage, Modelo aggregation, calculation, export, verification,
and TUI composition files require a narrow lease or an owner-applied patch.
Their occupancy does not block independent owned work.

## Steps

### Phase `P01` - Contracts and regression cases

Ground uncovered contracts and reproduce current acquisition-cost routing without changing shared integrations.

- [x] `P01.S01` - Ground and accept the missing identity, recorded-history, Modelo 130, and mixed-use-home contracts; `.vault/reference/2026-09-21-assets-core-ownership-contracts-reference.md, .vault/research/2026-09-21-assets-core-lifecycle-and-integration-research.md, .vault/adr/2026-09-21-assets-core-lifecycle-contract-adr.md`.
- [x] `P01.S02` - Reproduce and lock the current ordinary-expense, stock, and amortizable-category acquisition-cost behavior; `src/cadrumo/domain/renta/tests/, src/cadrumo/application/aggregation/tests/`.

### Phase `P02` - Schedule and persisted history

Implement the legally governed schedule, lifecycle model, and encrypted replayable history as one backend slice.

- [x] `P02.S03` - Implement legally grounded asset facts and deterministic schedule boundaries; `src/cadrumo/domain/renta/actividad_asset/, src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml, dev/registry/tests/test_modelo_100_activity_asset_amortization_parameters.py`.
- [x] `P02.S04` - Implement encrypted asset history, reopening, correction, and lifecycle persistence; `src/cadrumo/application/actividad_asset/, src/cadrumo/adapters/persistence/profile/actividad_asset.py, src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py, src/cadrumo/adapters/persistence/storage/namespace_registry.py`.

### Phase `P03` - Resolver and deduction safety

Enroll the authoritative source and integrate M130 and M100 with explicit collision and incompleteness behavior.

- [ ] `P03.S05` - Enroll the typed asset-schedule source and refuse incomplete or competing amortization claims; `src/cadrumo/domain/calculations/registry/, src/cadrumo/application/calculations/actividad_asset_schedule.py, src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`.
- [ ] `P03.S06` - Integrate annual and year-to-date deductions into Modelo 100 and Modelo 130; `src/cadrumo/application/aggregation/modelo_bindings.py, src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py, src/cadrumo/application/aggregation/renta_gasto_ledger.py`.

### Phase `P04` - IVA linkage and filing integration

Preserve independent IVA treatment while proving the persisted acquisition through verified filing artifacts.

- [ ] `P04.S07` - Link acquisitions reciprocally without merging IRPF assets and IVA bienes-inversion; `src/cadrumo/domain/transactions/models.py, src/cadrumo/application/ledger/actions_manual.py, src/cadrumo/domain/bienes_inversion/, src/cadrumo/application/renta/actividad_asset/`.
- [ ] `P04.S08` - Prove calculation, verification, provenance, and validated export for asset-derived deductions; `src/cadrumo/application/modelo/, src/cadrumo/application/filing/, src/cadrumo/application/modelo/tests/`.

### Phase `P05` - Frontend operations and acceptance

Expose shared operations through CLI and TUI and prove AS1-AS12 in isolated installed journeys.

- [ ] `P05.S09` - Expose shared asset operations through the established CLI hierarchy; `src/cadrumo/entrypoints/cli/_app_ledger_actividad_asset_command_specs.py, src/cadrumo/entrypoints/cli/_actividad_asset_cli.py, src/cadrumo/entrypoints/cli/tests/`.
- [ ] `P05.S10` - Expose shared asset operations through TUI composition without frontend arithmetic; `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py, src/cadrumo/entrypoints/tui/ledger/models.py, src/cadrumo/entrypoints/tui/ledger/routes.py, src/cadrumo/entrypoints/tui/tests/`.
- [ ] `P05.S11` - Implement isolated AS1-AS12 acceptance scenarios and independent financial oracles; `dev/acceptance/assets/, dev/acceptance/tests/`.
- [ ] `P05.S12` - Run integrated quality gates and complete the final architecture review; `.vault/audit/2026-09-21-assets-core-audit.md, affected source and test paths`.

## Parallelization

P01.S01 and P01.S02 may run concurrently with disjoint writers. P02.S03 starts
after P01.S01 accepts the required contracts; P02.S04 follows the stable domain
shape. P03 follows the coherent P02 backend. P04.S07 may prepare an owner-applied
linkage patch while P03 runs, but lands only after the identity contract is
accepted. P04.S08 follows P03 and the required shared-file leases. P05.S09 and
P05.S10 may run concurrently after application operations stabilize, with
disjoint CLI and TUI writers. P05.S11 follows both frontend projections and
P05.S12 is the integrated close.

Named assignments use Luna Max for bounded discovery, Terra High for principal
contract implementation, Terra Max for bounded code and verification, and one
Sol High adviser for unresolved architecture. Every worker preserves concurrent
changes and owns only its stated paths. The lead integrates all results and owns
campaign completion.

## Verification

- Focused schedule tests prove regime and authority selection, partial periods,
  year boundaries, remaining-base limits, final rounding, free-depreciation
  boundaries, mixed-use construction allocation, and land exclusion.
- Secure-persistence tests prove encrypted round trips, CAS behavior, replay,
  correction history, known and missing opening depreciation, disposal, and
  fully depreciated traceability.
- Real resolver tests prove material and intangible routing, transaction-ledger
  collision refusal, missing-data propagation, M130 year-to-date amounts, and
  single annual M100 inclusion with authoritative provenance.
- Installed CLI and TUI journeys prove create, inspect, correct, calculate, and
  export independently and in both continuation directions using isolated
  encrypted stores.
- AS1-AS12 each finish as proven, failed, blocked, or not exercised in a
  sanitized ACCEPTANCE-01 receipt with pinned source, package, and authority.
- Affected Ruff, strict typing, import-boundary, registry, export, and focused
  pytest gates pass under globally reserved commands, followed by a cohesive
  Phase-close and final review with no critical or high findings.
