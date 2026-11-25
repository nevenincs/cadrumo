---
tags:
  - '#plan'
  - '#runtime-operation-timing'
date: '2026-11-15'
tier: L1
related:
  - '[[2026-10-27-robust-logging-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
modified: '2026-11-15'
body_schema: body-v2
body_hash: 'sha256:6fcb21aa22879a63275e5686f12e45c1df6f8acab17035373e7167c34570761f'
---

# `runtime-operation-timing` plan

## Description

Approved 2026-11-15

Authorization: the operator's OPTIMIZATION brief and PRIME's explicit 05:07 order require this instrumentation unit alone for INTEGRATOR by 06:00. The accepted robust-logging decision governs bounded background scrubbed diagnostics; the accepted tui-architecture decision governs operation lifecycle and settlement semantics. This is execution within those decisions, without a new protocol, persisted schema, admission rule or costly architecture choice.

Emit producer-observed epoch milliseconds with only stage, opaque operation identity and registered definition. Admission follows successful journal creation; running follows the first committed RUNNING transition; settled follows committed terminal settlement and cleanup. Running does not claim worker readiness. Preserve richer existing settlement diagnostics and all journals, receipts, tax behavior, admission and custody protections.

## Steps

- [x] `S01` - Emit scrubbed admitted running and settled timestamps after committed transitions with real-journal ordering privacy replay and refusal tests; `src/cadrumo/application/operations and src/cadrumo/adapters/persistence/operations/tests/test_supervisor_lifecycle_timing.py`.
- [x] `S02` - Regenerate the stale import census separately to enroll existing modules and the lifecycle timing helper; `dev/quality/metadata/import_load_targets.json and its cadrumo cadrumo_runtime and dev partitions`.

## Parallelization

S01 precedes S02. PRIME 05:22 requires S02 to contain generated census output only; its ledger and review bookkeeping join the source commit as an explicit exception to per-Step metadata co-commit. The generator was run once on the stable current tree. S01 is sequential. The gpt-6-astra medium architect owns lifecycle_timing.py, supervisor_submission.py, supervisor_execution.py, settlement_snapshot.py and the real-journal timing test. The orchestrator owns this plan, ledger, audit, generated import targets and shared checks. Terra and Luna provide read-only evidence. ACCEPTANCE's dev tooling and DESKTOP's native files stay separately owned. Git mutations are serialized under .tmp/LANE-GIT.lock, staging only owned paths.

## Verification

Exercise the real supervisor with encrypted journal and lease fixtures. Assert admitted/running/settled ordering, integer epoch milliseconds at production time, successful and refused terminal parity, replay without duplicate admission, rejected admission without timing, bounded safe diagnostic fields and terminal progress despite a failing sink. Retain existing richer settlement diagnostics. Timing records are best-effort observations, never authority or commit fences.

Run focused owning tests, Ruff and format checks, configured type checks and import-boundary gate. Regenerate import-load targets for the new production module. Review the completed diff and evidence once before handoff. No calculation or projection changes are included; native build-17 correlation remains DESKTOP's acceptance evidence. Report worker startup and other unresolved span boundaries honestly.
