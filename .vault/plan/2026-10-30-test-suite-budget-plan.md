---
tags:
  - '#plan'
  - '#test-suite-budget'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
modified: '2026-10-31'
body_schema: body-v2
body_hash: 'sha256:0af69ce09a2761f762e84b922f019eb76da1d23ee631a6f83a1e247f4111e7df'
---

# `test-suite-budget` plan

## Description

Approved 2026-10-30

The operator asked to cut the full test lane from about 3.5 hours to 30 minutes, reduce the suite to what it needs, and remove all copy-paste from the test trees. That request authorizes these Steps. Coverage: `2026-08-14-test-harness-sanity-successor-adr` governs fixture ownership and worker width, and S08 amends its width.

Measured baseline, 2026-10-30, on a shared loaded box: 67,703 collected tests in 6,068 files and 76,213 worker-seconds. The phase split is call 87.7%, setup 11.4%, teardown 0.9%. Tests under 0.05s number 44,669 and total 359s; the 6,070 tests over 2s hold 92% of the time. The 30-minute target means 21,600 worker-seconds at 12 workers.

Speed comes first from removing repeated work in the slowest tests. A removal needs evidence that nothing the test proves is lost; official examples, independent oracles and refusal paths are not cut on overlap alone.

Constraint on reuse: secure stores stay per test. `2026-07-04-codebase-solidification-audit` disproved the June module-scope hoist, because the store persists a bucket directory, manifest, wrapped-DEK keystore, SQLite database and catalogue on disk, and sharing it let persisted IDs bleed between tests and silenced idempotency and anti-tautology assertions. A savepoint rollback cannot reset those artefacts. Steps may share only stateless work (operation composition, compiled registries, built inputs) at worker or module scope, as S01 does. Where store setup is the cost, build and seal a template store once per worker, then copy it into each test's own `tmp_path` and open a fresh runtime on the copy; never hand one live store, repository or keystore to two tests.

## Steps

- [x] `S01` - Compose the conformance runtime once per worker instead of per case: registered-executor conformance and subject binding (7,100s); `src/cadrumo/entrypoints/tests/registered_executor_case_support.py`.
- [ ] `S02` - Share the remaining per-case composition across the actor-by-frontend and parity families (about 3,500s); `src/cadrumo/entrypoints/tests`.
- [ ] `S03` - Reuse one compiled tree across generated-export trees and inheritance cases (2,500s); `dev/registry/pipeline/tests`.
- [ ] `S04` - Replace per-defect real-gate launches in the import quality gate with one shared baseline (2,255s); `dev/tests/test_import_quality_gate.py`.
- [ ] `S05` - Bound TUI sequence walks and workbench acceptance to one composed app per module (2,800s); `dev/tui/harness/tests, src/cadrumo/entrypoints/tui/tests`.
- [x] `S06` - Reduce the per-command CPU floor and repeated calculation cost on the product CLI path; `src/cadrumo_client, src/cadrumo_runtime, src/cadrumo/application/modelo`.
- [ ] `S07` - Stop seeding test state through whole CLI commands where the command is not the subject; `src/cadrumo_runtime/host/tests/frontend/cli, src/cadrumo/entrypoints/tests/profile_persistence`.
- [ ] `S08` - Raise the default worker width to the measured best and amend the worker decision; `src/cadrumo/tests/worker_count_hook.py`.
- [ ] `S09` - Remove whole-function and token-level clones across test trees; `src, dev test trees`.
- [ ] `S10` - Prune redundant tests by per-test coverage and mutation evidence on critical modules; `src, dev test trees`.
- [ ] `S11` - Add a lane time budget and per-test ceiling so the suite cannot drift back; `justfile, dev/test_runs`.

## Parallelization

S02, S03, S04 and S05 run concurrently with disjoint write scopes: S02 `src/cadrumo/entrypoints/tests` plus `dev/operation_contract_manifest/tests`; S03 `dev/registry`; S04 `dev/tests`, `dev/docs/tests`, `dev/locales/tests` and `dev/packaging/tests`; S05 `dev/tui` and `src/cadrumo/entrypoints/tui`. Workers commit their own paths. The orchestrator serializes ledger rows and Step closure. S08 and S10 wait until these finish, because width and pruning measurements need a stable suite.

## Verification
