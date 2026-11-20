---
tags:
  - '#exec'
  - '#ledger-classify-queue'
date: '2026-11-20'
modified: '2026-11-20'
body_schema: 'body-v2'
body_hash: 'sha256:895e3171635127c19b29c5877509e6d8136c8e0ead5fd03a3ecfa3260ffd8620'
related:
  - "[[2026-11-20-ledger-classify-queue-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `ledger-classify-queue` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S02` `M` `src/cadrumo/entrypoints/ledger_llm_composition.py`
- `S02` `A` `src/cadrumo/application/ledger/off_host_consent_refusal.py`
- `S02` `M` `src/cadrumo/application/operations/next_step.py`
- `S02` `A` `native/desktop/frontend/src/components/ledger/inspector/ConsentRemedies.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/inspector/ModelSuggestion.tsx`
- `S02` `M` `native/desktop/frontend/src/components/ledger/inspector/SelectionInspector.tsx`
- `S02` `verify:` `pytest test_ledger_classification_reader_refusal_settlement` -> `pass`
- `S02` `verify:` `playwright ledger-model-refusal` -> `pass`
- `S07` `M` `cadrumo-agent src/cadrumo_agent/providers/declared_catalog.py`
- `S07` `A` `cadrumo-agent src/cadrumo_agent/providers/background_task_kinds.py`
- `S07` `verify:` `cadrumo-agent just check-python` -> `pass`
- `S07` `verify:` `cadrumo-agent just check-type` -> `pass`
- `S03` `A` `src/cadrumo/domain/transactions/classification_job.py`
- `S03` `A` `src/cadrumo/application/ledger/classification_job_repository.py`
- `S03` `A` `src/cadrumo/adapters/persistence/profile/classification_jobs.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S03` `verify:` `pytest classification_job tests + storage/errors/transactions` -> `pass`
- `S03` `verify:` `dev.quality.types --full` -> `pass`
- `S04` `A` `src/cadrumo/application/ledger/classification_job_operation.py`
- `S04` `A` `src/cadrumo/application/ledger/classification_job_read_operation.py`
- `S04` `A` `src/cadrumo/application/ledger/classification_job_contracts.py`
- `S04` `M` `src/cadrumo/entrypoints/operation_composition_ledger.py`
- `S04` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S04` `A` `native/desktop/frontend/src/shell/ledgerClassificationJobContract.ts`
- `S04` `verify:` `pytest classification job operations + ledger/operations/errors (1186)` -> `pass`
- `S04` `verify:` `manifest --check` -> `pass`
- `S04` `verify:` `relay_contracts --check` -> `pass`
- `S08` `M` `src/cadrumo_agent_service/providers/application/model_runs.py`
- `S08` `M` `src/cadrumo_agent_service/providers/domain/record.py`
- `S08` `M` `src/cadrumo_client/contracts/model_runs.py`
- `S08` `M` `src/cadrumo_runtime/host/operation_authority.py`
- `S08` `M` `src/cadrumo/adapters/outbound/llm/text_classifier.py`
- `S08` `verify:` `pytest cadrumo_agent_service + client/runtime/llm/runtime_lifecycle (1895)` -> `pass`
- `S08` `verify:` `dev.quality.types --full` -> `pass`
- `S09` `A` `native/desktop/frontend/src/components/settings/TaskModels.tsx`
- `S09` `A` `native/desktop/frontend/src/shell/taskModels.ts`
- `S09` `A` `native/desktop/frontend/tests/scenarios/task-models.spec.ts`
- `S09` `verify:` `playwright task-models, agent-readers, local-models, agent-settings-sections, ledger-reading-model (36)` -> `pass`
- `S05` `A` `src/cadrumo/application/ledger/classification_job_run.py`
- `S05` `A` `src/cadrumo/entrypoints/tests/test_ledger_classification_job_run.py`
- `S05` `M` `src/cadrumo/entrypoints/ledger_llm_composition.py`
- `S05` `M` `native/desktop/src-tauri/src/shell/ledger/admitted.rs`
- `S05` `verify:` `pytest job run+operations (46)` -> `pass`
- `S05` `verify:` `desktop-host-unit-test (1048)` -> `pass`
- `S06` `A` `src/cadrumo/domain/evidence_consent/grant.py`
- `S06` `A` `src/cadrumo/application/ledger/classification_job_consent_operation.py`
- `S06` `A` `src/cadrumo/application/ledger/classification_job_apply_operation.py`
- `S06` `M` `src/cadrumo/adapters/persistence/llm/consent_ledger.py`
- `S06` `M` `native/desktop/src-tauri/src/shell/ledger/admitted.rs`
- `S06` `verify:` `pytest consent/run/operations/evidence_consent/errors (194)` -> `pass`
- `S06` `verify:` `desktop-host-unit-test (1048)` -> `pass`
- `S10` `A` `native/desktop/src-tauri/src/shell/background_tasks.rs`
- `S10` `M` `native/desktop/src-tauri/src/shell/ledger/mod.rs`
- `S10` `M` `native/desktop/src-tauri/src/shell/ledger/admitted.rs`
- `S10` `A` `native/desktop/frontend/src/shell/backgroundTasksContract.ts`
- `S10` `verify:` `desktop-host-unit-test (1061)` -> `pass`
- `S10` `verify:` `cargo fmt --check` -> `pass`
- `S10` `verify:` `desktop-host-unit-clippy` -> `fail`

## Notes

- `S07` Landed on cadrumo-agent main 5b8bdea; Cadrumo pin moved in ec5b6375ee with the consumer (catalog v8, effort in agent.effort); no task-kind setting caller yet (S08)
- `S04` Broad sweep stopped as hung on PRIME order; focused tests only, broad sweeps left to QUALITY
- `S08` No cadrumo-agent change needed; no re-pin
- `S05` Tests written after code; defect-injection check done instead of fail-first. Off-host jobs refuse until S06.
- `S06` Tests written alongside code; defect injection substituted for fail-first. Apply commits per movement then the job once (non-atomic; re-apply refused as stale).
- `S10` clippy fails only on pre-existing `large_enum_variant` at agent/stream.rs:308 (tui 24e08b0f29). Gaps: no mid-run progress for runs started outside this window; auto-resume on profile open undecided (S11); list read returns whole jobs, limit 50.
