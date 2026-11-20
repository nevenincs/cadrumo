---
tags:
  - '#exec'
  - '#ledger-classify-queue'
date: '2026-11-20'
modified: '2026-11-20'
body_schema: 'body-v2'
body_hash: 'sha256:1009b392ed0b5eeb29e361422b50741f9633796e50ed8b6130cf980796ee784d'
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

## Notes

- `S07` Landed on cadrumo-agent main 5b8bdea; Cadrumo pin moved in ec5b6375ee with the consumer (catalog v8, effort in agent.effort); no task-kind setting caller yet (S08)
