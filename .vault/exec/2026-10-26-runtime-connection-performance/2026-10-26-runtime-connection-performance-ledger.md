---
tags:
  - '#exec'
  - '#runtime-connection-performance'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:77993b895d46036b30c6530acda0b272816710c699b318ee41ccea741c79d221'
related:
  - "[[2026-10-26-runtime-connection-performance-plan]]"
---

# `runtime-connection-performance` ledger

## Changes

- `S01` `M` `dev/ci/profile_wizard_benchmark.py`
- `S01` `verify:` `profile CLI baseline journey` -> `pass`
- `S01` `verify:` `synthetic Modelo 100 benchmark` -> `pass`
- `S03` `M` `src/cadrumo_runtime/host/worker_operation_requests.py`
- `S03` `M` `src/cadrumo_runtime/host/worker_service.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_worker_request_wait.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_worker_read_refusal.py`
- `S03` `M` `src/cadrumo_runtime/adapters/tests/test_server_idle_wait.py`
- `S03` `verify:` `owning worker regression tests` -> `pass`
- `S03` `verify:` `native dual channel wait regression` -> `pass`
- `S03` `verify:` `server idle shutdown tests` -> `pass`
- `S03` `verify:` `ruff changed files` -> `pass`
- `S03` `verify:` `just check-types` -> `pass`
- `S03` `verify:` `just check-registry-gate` -> `pass`
- `S03` `verify:` `just test-gate build/runtime-connection-review-20261026/changed-files.txt` -> `fail`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_entries.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_categorisation.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_evidence_files.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_registers.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_review.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_import.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/frontend/tui/ledger_invoices_runtime_harness.py`
- `S03` `verify:` `eight affected ledger modules: 490 tests` -> `pass`
- `S03` `verify:` `ruff lint and format seven ledger fixture files` -> `pass`
- `S03` `verify:` `scoped serial runtime lane: 15 tests` -> `pass`
- `S02` `A` `.vault/audit/2026-10-26-runtime-connection-performance-audit.md`
- `S02` `verify:` `CLI candidate benchmark: two tests` -> `pass`
- `S02` `verify:` `native transport load: ten tests` -> `pass`
- `S02` `verify:` `runtime-connection-performance vault check` -> `pass`
- `S02` `verify:` `just check-code (resumed)` -> `fail`
- `S02` `verify:` `ty check fourteen root-modified Python files` -> `pass`
- `S04` `M` `src/cadrumo/adapters/persistence/operations/journal.py`
- `S04` `M` `src/cadrumo/adapters/persistence/operations/tests/test_journal.py`
- `S04` `verify:` `initial journal lock regressions before fix` -> `fail`
- `S04` `verify:` `replay corruption regression before presence-aware fix` -> `fail`
- `S04` `verify:` `five final interleaving regressions` -> `pass`
- `S04` `verify:` `seven journal owning modules: 92 tests` -> `pass`
- `S04` `verify:` `filing-readiness isolated page after journal fix` -> `pass`
- `S04` `verify:` `ruff lint and format journal files` -> `pass`
- `S04` `verify:` `ty journal files` -> `pass`
- `S04` `verify:` `pyrefly journal module` -> `pass`
- `S04` `verify:` `basedpyright journal module` -> `pass`
- `S02` `verify:` `just test-pytest-harness (resumed): 4 passed, 2 failed` -> `fail`
- `S02` `verify:` `isolated filing-readiness before journal fix` -> `pass`
- `S02` `verify:` `isolated filing-readiness after journal fix` -> `pass`
- `S08` `M` `dev/ci/profile_wizard_benchmark.py`
- `S08` `A` `dev/ci/tests/test_profile_wizard_benchmark.py`
- `S08` `A` `src/cadrumo/entrypoints/cli/tests/test_profile_io_native.py`
- `S08` `verify:` `profile recorder unit tests (3 tests)` -> `pass`
- `S08` `verify:` `native profile read-edit-read (2 runs)` -> `pass`
- `S08` `verify:` `scoped Ruff and type checks` -> `pass`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/modelos_calculation.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`
- `S07` `verify:` `calculation repository owning suite (33 tests)` -> `pass`
- `S07` `verify:` `native Modelo benchmark candidate-modelo-s07` -> `pass`
- `S07` `verify:` `scoped Ruff ty pyrefly basedpyright` -> `pass`
- `S05` `A` `dev/ci/runtime_journal_benchmark.py`
- `S05` `A` `dev/ci/tests/test_runtime_journal_benchmark.py`
- `S05` `verify:` `journal observer tests (5 tests)` -> `pass`
- `S05` `verify:` `journal observer Ruff format ty` -> `pass`
- `S05` `verify:` `native filing-readiness isolated and eight concurrent pages` -> `pass`
- `S05` `verify:` `eight concurrent pages after deferred diagnostics` -> `pass`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/journal.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/tests/test_journal.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/tests/test_financial_journal_purge.py`
- `S06` `M` `src/cadrumo/core/locks.py`
- `S06` `M` `src/cadrumo/core/tests/test_locks_diagnostics.py`
- `S06` `verify:` `journal owning tests (95 tests)` -> `pass`
- `S06` `verify:` `lock owning tests (25 tests)` -> `pass`
- `S06` `verify:` `scoped lint formatting ty pyrefly basedpyright` -> `pass`
- `S06` `verify:` `post-fix eight concurrent native filing-readiness pages` -> `pass`
- `S08` `M` `dev/ci/modelo_runtime_benchmark.py`
- `S08` `M` `dev/ci/tests/test_modelo_runtime_benchmark.py`
- `S08` `verify:` `combined benchmark instrumentation tests (18 tests)` -> `pass`
- `S08` `verify:` `scoped benchmark Ruff format ty` -> `pass`
- `S08` `verify:` `native Modelo admission phases profile and logging journeys` -> `pass`

## Notes

- `S01` No commit: shared worktree contains overlapping peer changes and candidate source is not an isolated revision. Payload-free measurements retained in the audit and ignored build outputs.
- `S03` Broad gate stopped at two CI contract failures in unchanged recipe/temp-root files; remaining scoped stages run separately. Root changes overlap peer-owned uncommitted source/test prerequisites; no whole-file staging or commit.
- `S03` The original broad parallel runtime/code/harness tool sessions disappeared without verdicts. Focused ledger coverage now passes; code and harness aggregates restarted.
- `S02` No end-to-end speedup established: shared-host and concurrent-source variance. Candidate Modelo, TUI end-to-end and Rust execution not verified. Review remains pending broader required checks; no commit because source overlaps peer work.
- `S02` Aggregate saw concurrent source edits: graph census changed and a file was temporarily unparsable; remaining lint/type/reachability/symbol/export failures name other files. Whole-workspace verification remains pending; no passing aggregate claim.
- `S04` Three crashed-owner fixture pipe-finalizer warnings recorded. Whole-workspace/corpus gate failures and concurrent source drift remain; no end-to-end speedup or complete elimination of write contention claimed. No commit: preserve overlapping peer work and keep the integrated patch reviewable.
- `S02` Harness golden tier rejected concurrent input drift; coherence exposed three 30-second journal-lock timeouts plus bounded operation/deadline outcomes. Captured lock holds exceeded38seconds. S04 removes read-only decode from exclusion and fixes replay error classification; remaining write-side contention and stable full-corpus verification unresolved.
- `S08` No production authentication fix justified; startup includes child observer imports. Changes uncommitted to preserve overlapping peer work.
- `S07` Repeated full catalogue counts remain22loads/23decodes; candidate15.305seconds decode,344MB processed. No end-to-end speedup claim.
- `S05` Historical39-second phases unavailable. New16.7606second hold attributes9.4763seconds fsync,6.8429seconds logging,0.4374seconds replace. Afterfix978holds and zero logging-under-lock spans; max1.0648seconds. No causal shared-host speedup claim.
- `S06` Partial step: full original concurrent corpus not reverified; fsync and write serialization remain under exclusion. No commits due overlapping peer work.
- `S08` Intermittent admission delay remains unassigned: prior 29-second pre-password gap did not recur with buffered logging instrumentation. Latest human admission 4.182 seconds includes 1.774 seconds benchmark setup. No production latency guarantee.
