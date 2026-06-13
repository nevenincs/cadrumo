---
tags:
  - '#plan'
  - '#modelo-work-revision-cli-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
  - '[[2026-06-05-modelo-addressing-ux-follow-up-queue-adr]]'
  - '[[2026-06-05-modelo-addressing-ux-code-review-audit]]'
---


# `modelo-work-revision-cli-decomposition` `revision command extraction` plan

## Description

Continue decomposing the legacy modelo CLI root after the completed Modelo Addressing UX plan. This plan extracts revision listing, revision display, verify, and file command registration into focused CLI modules while preserving the accepted natural-key addressing contract. CLI modules remain transport consumers of the top-level application facades; no command body may own work-unit selection, revision-pick policy, registry authority, calculation behavior, verification policy, or filing policy.

W04 extends the plan to execute the residual guard findings discovered during closure. It targets only the broad CLI monolith guard offenders that blocked full guard success after W03: `_app_live.py` and `_ledger.py`. The residual wave must shrink those roots through focused command registrars, not by raising stale budgets or weakening the guard.

## Wave `W01` - revision read surface extraction

Extract read-only calculation revision commands from the legacy root so revision listing and display become focused transports over application services and centralized addressing.

### Phase `W01.P01` - revision read baseline

Inventory the current revision read command surface and prove the extraction is covered by the accepted addressing ADR.

- [x] `W01.P01.S01` - inventory `work revisions` and `work revision` command dependencies and rendering helpers; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P01.S02` - run exact and semantic discovery for revision read command selector and id linkage; `src/aeat/entrypoints/cli`.

### Phase `W01.P02` - revision read registrar

Move revision listing and revision display command registration into a focused CLI module without changing command names, flags, payloads, or selector behavior.

- [x] `W01.P02.S03` - extract `work revisions` and `work revision` into a focused registrar; `src/aeat/entrypoints/cli/_modelo_work_revision_cli.py`.
- [x] `W01.P02.S04` - replace legacy revision read command bodies with registrar mounting only; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P02.S05` - cover revision read extraction with real CLI behavior and architecture guard tests; `src/aeat/entrypoints/cli`.

## Wave `W02` - verify and file command extraction

Extract mutating revision lifecycle commands after the read surface is separated, keeping verification and filing policy in backend application services.

### Phase `W02.P03` - verify file registrar

Move verify and file command registration into a focused CLI module that consumes centralized revision addressing and application services.

- [x] `W02.P03.S06` - extract `work verify` and `work file` into a focused registrar; `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `W02.P03.S07` - replace legacy verify and file command bodies with registrar mounting only; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W02.P03.S08` - preserve workflow gate and command-specific revision default behavior through application facades; `src/aeat/application/modelo`.
- [x] `W02.P03.S09` - cover verify and file extraction with real CLI behavior and workflow gate tests; `src/aeat/entrypoints/cli`.

## Wave `W03` - verification and ratchet closure

Close the slice with guards, evidence, review, and size-budget ratcheting.

### Phase `W03.P04` - closure gates

Prove the extracted revision commands remain thin transports and that the legacy root shrinks.

- [x] `W03.P04.S10` - lower `_modelo.py` and command budget guards after extraction; `src/aeat/entrypoints/cli/test_cli_module_size.py`.
- [x] `W03.P04.S11` - run exact and semantic audits for revision command business logic absence in CLI modules; `src/aeat/entrypoints/cli`.
- [x] `W03.P04.S12` - persist code review and final step records for the revision decomposition slice; `.vault/audit`.

## Wave `W04` - residual monolith guard closure

Eliminate the remaining broad CLI monolith guard offenders found during W03 by decomposing unrelated live and ledger CLI surfaces into focused transport modules, preserving backend-owned business policy and public application facade consumption.

### Phase `W04.P05` - live residual extraction

Shrink the live CLI root below its frozen guard by moving a coherent command group into a focused CLI registrar without moving live capture or verification policy out of application services.

- [x] `W04.P05.S13` - inventory live CLI command groups and select the smallest coherent extraction that clears the frozen line budget; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W04.P05.S14` - extract selected live command group into a focused registrar and mount it from the live root; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [x] `W04.P05.S15` - verify selected live command behavior and live root size after extraction; `src/aeat/entrypoints/cli/test_live_* src/aeat/entrypoints/cli/test_cli_module_size.py`.

### Phase `W04.P06` - ledger residual extraction

Shrink the ledger CLI root below its frozen guard by moving a coherent command group into a focused CLI registrar without introducing CLI-owned accounting policy.

- [x] `W04.P06.S16` - inventory ledger CLI command groups and select the smallest coherent extraction that clears the frozen line budget; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W04.P06.S17` - extract selected ledger command group into a focused registrar and mount it from the ledger root; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W04.P06.S18` - verify selected ledger command behavior and ledger root size after extraction; `src/aeat/entrypoints/cli/test_ledger_* src/aeat/entrypoints/cli/test_cli_module_size.py`.

### Phase `W04.P07` - residual guard closure

Ratchet and verify the residual guard offenders so the broad production CLI monolith guard passes for the first time in this slice.

- [x] `W04.P07.S19` - ratchet live and ledger line budgets after residual extraction; `src/aeat/entrypoints/cli/test_cli_module_size.py`.
- [x] `W04.P07.S20` - run broad CLI monolith guard and focused residual behavior gates; `src/aeat/entrypoints/cli`.
- [x] `W04.P07.S21` - persist residual closure audit and final plan state; `.vault/audit .vault/exec .vault/plan/2026-06-05-modelo-work-revision-cli-decomposition-plan.md`.
- [x] `W04.P07.S22` - align residual verification with the active hexagonal pytest marker taxonomy; `src/aeat/tests/_marker_hook.py conftest.py`.

## Parallelization

Waves are ordered. W01 must land before W02 because verify and file share revision-selection helpers and payload conventions with the read commands. W04 runs after W03 because it is a residual closure wave driven by the broad monolith guard failure, not by the modelo addressing ADR itself. Within a phase, tests and exact discovery may run in parallel with static lint only after the code edit for that phase is complete. Plan state updates and step records must remain serialized.

## Verification

The plan is complete when every W01 through W04 step is closed, `vaultspec-core vault plan check` passes, focused real-behavior CLI tests pass, architecture boundary tests pass, locale gates remain clean when touched, exact `rg` discovery shows no new CLI-local selector policy, serialized `vaultspec-rag` discovery confirms application facade consumption, `_modelo.py` has a lower frozen size budget than the previous 2242-line baseline, and the broad production CLI monolith guard passes without unrelated residual offenders.
