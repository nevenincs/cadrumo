---
tags:
  - '#plan'
  - '#ledger-classify-queue'
date: '2026-11-20'
tier: L2
related:
  - '[[2026-11-20-ledger-classify-queue-adr]]'
modified: '2026-11-20'
body_schema: body-v2
body_hash: 'sha256:9e92835fa1142c5c300c444de4b47c47f42311e15569fc97ccfc961755e4a692'
---

# `ledger-classify-queue` plan

## Description

Approved 2026-11-20

**Authorization.** PRIME, the orchestrator of this session, handed over the LEDGER-CLASSIFY brief. It relays the operator's binding requirements of 2026-11-20.

**Scope.**

- The classification pipeline and the job queue.
- The completion signal.
- Per-task model defaults.
- The Libro agent actions.

Anything that touches `components/ledger/inspector/*` is coordinated with the LEDGER-IVA-EDIT session in the same worktree.

**Decision coverage.** `2026-11-20-ledger-classify-queue-adr` governs this plan. Its 2026-11-20 amendments change four earlier records: `2026-10-25-agent-owned-models-adr`, `2026-10-04-desktop-shell-adr`, `2026-10-16-idle-churn-adr` and `2026-10-17-idle-churn-operation-observation-adr`. The evidence is `2026-11-20-ledger-classify-queue-reference`.

How the ADR's constraints map to the phases:

| ADR constraint | Phase |
| --- | --- |
| 9 (baseline) | P01 |
| 6 (consent refusal shown to the person) | P01 |
| 3 to 6 (jobs, proposals, restart, consent) | P02 |
| 1 and 2 (task-kind defaults and effort) | P03 |
| 7 and 8 (cue, indicator, row state) | P04 |
| 9 (optimisation) | P05 |

These decisions apply unchanged:

- Model output is a proposal (`2026-06-04-llm-ledger-classification-adr`, `2026-06-15-llm-classification-workflow-adr`).
- Consent scopes follow `2026-06-10-llm-evidence-classification-adr` and its 2026-10-13 amendment.

**Landing.** Each phase lands on feature/tui once its checks pass, and the SHA goes to PRIME.

## Steps

### Phase `P01` - Baseline and visible consent

Measure classification speed before changing it, and stop off-host refusals from reading as an unavailable model.

- [ ] `P01.S01` - Measure time to first result for one movement and throughput for 100 and 1000 synthetic movements through the real classify path on the local lane, recording method and numbers; `dev/measure/ledger_classification_speed.py, .vault audit`.
- [ ] `P01.S02` - Translate LLMConsentError into a typed consent_required refusal with authorise and switch-to-local remedies, and render its cause in ModelSuggestion and the selection ask; `src/cadrumo/application/ledger/ledger_llm_composition.py, llm_review_execution.py, frontend components/ledger/inspector/ModelSuggestion.tsx, SelectionInspector.tsx, inspectorWords.ts, locales`.

### Phase `P02` - Backend job queue

Persist classification jobs with per-item proposals, worked by a cooperative resumable operation.

- [ ] `P02.S03` - Declare the classification job record, its secure namespace and repository with revision-guarded writes; `src/cadrumo/domain/transactions/classification_job.py, adapters/persistence/storage/secure_object_namespaces.py, namespace_registry.py, adapters/persistence/profile/classification_jobs.py`.
- [ ] `P02.S04` - Register enqueue, read, cancel, retry and dismiss operations with generated contracts and the manifest regenerated; `src/cadrumo/application/ledger/classification_job_*.py, operation_composition_ledger.py, operation contract manifest`.
- [ ] `P02.S05` - Register the cooperative resumable run operation that classifies pending items, commits proposals per batch and reconciles interrupted items as UNKNOWN; `src/cadrumo/application/ledger/classification_job_run.py, ledger_llm_composition.py`.
- [ ] `P02.S06` - Bind consent per job with once, session and remembered scopes for off-host lanes and apply proposals through the existing review and apply path; `src/cadrumo/adapters/outbound/llm/consent.py, application/ledger/classification_job_*.py, llm_review_execution.py`.

### Phase `P03` - Task-kind models and effort

cadrumo-agent serves task kinds and background effort; the agent service resolves a task setting before the picker.

- [ ] `P03.S07` - Serve task kinds and a background effort option in cadrumo-agent's catalogue on a cadrumo-agent branch merged to its main; `cadrumo-agent catalogue and background run sources`.
- [ ] `P03.S08` - Store per-task-kind lane, model and effort in model-role-selections, resolve task setting before the picker, send effort, and re-pin cadrumo-agent; `src/cadrumo_agent_service/providers, adapters/agent_background_runs.py, _data/agent_api/pin.json`.
- [ ] `P03.S09` - Offer the per-task-kind setting in the agent settings surface from served vocabulary; `native/desktop/frontend agent settings components, generated agent catalogue contract`.

### Phase `P04` - Signal, indicator and Libro actions

Typed revision cue from host to window, background-task indicator, per-row state and per-row agent actions.

- [ ] `P04.S10` - Add the background-task cue channel mapping RecordsChanged to a revision read and a typed cue, and drive job runs outside the serial lock; `native/desktop/src-tauri/src/shell/background_tasks.rs, shell/ledger/mod.rs, generated contract`.
- [ ] `P04.S11` - Add the shell background-task indicator with progress, failures, cancel and retry, re-reading on cue, subscribe and focus; `native/desktop/frontend/src/shell/backgroundTasks.ts, components/shell/BackgroundTasks.tsx, locales`.
- [ ] `P04.S12` - Show per-row classifying, proposed and failed state in the Libro grid and re-read the ledger window on the cue; `frontend shell/ledgerWindow.ts, components/ledger grid`.
- [ ] `P04.S13` - Add per-row and selection Preguntar al agente actions that enqueue jobs, retire the 20-row loop, and add open in agent conversation; `frontend components/ledger grid and SelectionInspector.tsx, agent panel handoff`.

### Phase `P05` - Speed

Optimise against the P01 baseline and report numbers before and after.

- [ ] `P05.S14` - Batch items per request, bound concurrency by lane capability, share the prompt prefix and warm the local model, keeping only measured gains; `src/cadrumo/application/ledger/classification_job_run.py, adapters/outbound/llm/text_classifier.py`.
- [ ] `P05.S15` - Remeasure with the P01 method and record before and after numbers; `dev/measure/ledger_classification_speed.py, .vault audit`.

## Parallelization

**Ordering.**

- P01.S01 and P01.S02 run in parallel.
- P02 is sequential: S03, then S04, then S05 and S06.
- P03.S07 is cadrumo-agent work and runs in parallel with P02.
- P03.S08 follows S07's merge to cadrumo-agent main, and never pins an unpushed commit. S09 follows S08.
- P04.S10 needs the read operation from P02.S04. S11 to S13 follow S10.
- P05 follows P02 and P04.

**Ownership.**

- The orchestrator owns commits, the plan and the ledger. Subagents write only the paths in their brief.
- The LEDGER-IVA-EDIT session owns:
  - `components/ledger/inspector/ClassifySection.tsx`, `MovementInspector.tsx` and `InspectorField.tsx`;
  - the ledger dev fixtures;
  - `ledgerApply.ts`;
  - its uncommitted locale edits.
- Locale additions wait until those edits are committed, and then commit as whole files.

## Verification

Tests fail first at each layer, go through the real composition, use synthetic data and run with `CADRUMO_PYTEST_WORKERS=4`.

**P01.**

- The measurement states which layers were real.
- The consent refusal is typed and is shown with its cause and remedies.

**P02.**

- Enqueue, cancel, retry and dismiss each have success and refusal tests: revision conflict, unknown job, and missing consent on an off-host lane.
- The run operation resumes after an interruption.
- An interrupted item reads `UNKNOWN`, not done.
- No ledger fact is written.
- A proposal becomes stale when its movement changes.
- The operation contract manifest and the generated TS contracts are fresh.

**P03.**

- On the cadrumo-agent side, the catalogue serves task kinds and the effort option.
- On the service side:
  - the task setting resolves before the picker;
  - the existing capability refusals are kept;
  - effort is sent only when the lane declares it.
- The pin points at a pushed commit.

**P04.**

- wdio specs cover:
  - the indicator showing progress and a failure with its cause;
  - a cue changing the view without polling;
  - a re-read on focus;
  - per-row state;
  - each per-row action opening a job or a typed refusal.
- A host test covers the revision-gated cue.

**P05.** Before and after numbers use the P01 method on the same machine and lane.

**Every step.** Run `ruff`, the root venv's `ty`, `npm run check` and the tests for the touched scope. Run `dev.quality.types --full` when a protocol changes, and `just check-import-boundaries` when imports cross packages.
