---
tags:
  - '#exec'
  - '#duplication-cluster-cleanup'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:c78b49487de355588845b4c06c262099f907437a67315a5e7f89d850e1a33a86'
related:
  - "[[2026-10-29-duplication-cluster-cleanup-plan]]"
---

# `duplication-cluster-cleanup` ledger

## Changes

- `S01` `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `S01` `verify:` `uv run --no-sync pytest -n 0 -m integration src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py -q` -> `pass`
- `S01` `verify:` `scoped Ruff check and format and Windows ty` -> `pass`
- `S01` `by:` `Terra 6.1 xhigh`
- `S02` `M` `src/cadrumo/application/modelo/workspace_schema.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_graded.py`
- `S02` `A` `src/cadrumo/application/modelo/workspace_baseline.py`
- `S02` `A` `src/cadrumo/application/modelo/tests/test_workspace_baseline.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_workspace.py`
- `S02` `verify:` `baseline/model/producer focused pytest 54 cases` -> `pass`
- `S02` `verify:` `real persistence work-review pytest 21 cases` -> `pass`
- `S02` `verify:` `static Workspace pytest 27 cases` -> `pass`
- `S02` `verify:` `five-file Ruff check and format and Windows ty` -> `pass`
- `S02` `verify:` `just generate-import-load-targets` -> `pass`
- `S02` `by:` `Sol 6.1 high`
- `S03` `M` `src/cadrumo/entrypoints/cli/app_live_commands.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_single.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_bulk.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_operation_filed_source.py`
- `S03` `verify:` `filed capture owning and complementary pytest 59 cases` -> `pass`
- `S03` `verify:` `scoped Ruff check and format and Windows ty` -> `pass`
- `S03` `by:` `Terra 6.1 xhigh`
- `S04` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/test_view_stream_relay.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/test_profile_connections.py`
- `S04` `verify:` `runtime view stream integration pytest 26 cases` -> `pass`
- `S04` `verify:` `runtime profile connections integration pytest 5 cases` -> `pass`
- `S04` `verify:` `three-file Ruff check and format and Windows ty` -> `pass`
- `S04` `by:` `Terra 6.1 xhigh`
- `S05` `M` `src/cadrumo/application/workbench_generation_reader.py`
- `S05` `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `S05` `verify:` `workbench generation and capture-memory pytest 46 cases` -> `pass`
- `S05` `verify:` `workbench capture order and phase controls 5 cases` -> `pass`
- `S05` `verify:` `two-file Ruff check and format and Windows ty` -> `pass`
- `S05` `by:` `Sol 6.1 high`
- `S05` `verify:` `parent combined Ruff and formatting and Windows ty on 19 cleanup files` -> `pass`
- `S06` `M` `src/cadrumo/application/auth/operator_cleanup.py`
- `S06` `M` `src/cadrumo/application/auth/operator_revocation.py`
- `S06` `A` `src/cadrumo/application/auth/tests/test_operator_cleanup_matching.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_operator_transaction_recovery.py`
- `S06` `verify:` `auth matching and real durable cleanup combined pytest 58 cases` -> `pass`
- `S06` `verify:` `exact transaction concurrency case pytest 1 case` -> `pass`
- `S06` `verify:` `four-file Ruff check and format and Windows ty` -> `pass`
- `S06` `verify:` `unchanged duplication scanner post-refinement no auth pair` -> `pass`
- `S06` `by:` `Sol 6.1 high`
- `S07` `M` `src/cadrumo/entrypoints/tests/test_reader_consumer_gating.py`
- `S07` `verify:` `reader gating focused regression pytest 1 case` -> `pass`
- `S07` `verify:` `reader consumer gating owning integration pytest 41 cases` -> `pass`
- `S07` `verify:` `scoped Ruff and format and Windows ty` -> `pass`
- `S07` `by:` `Terra 6.1 xhigh`
- `S02` `verify:` `relative canonical baseline import owning integration pytest 27 cases` -> `pass`
- `S02` `verify:` `relative import correction Ruff format and Windows ty` -> `pass`
- `S04` `verify:` `exact current relay integration suite after foreign test-helper migration 26 cases` -> `pass`
- `S04` `verify:` `exact current relay Ruff format and Windows ty` -> `pass`
- `S08` `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_import_reader_refusal_settlement.py`
- `S08` `verify:` `PDF reader refusal focused regression pytest 1 case` -> `pass`
- `S08` `verify:` `ledger reader refusal settlement owning integration module pytest 4 cases` -> `pass`
- `S08` `verify:` `scoped Ruff format and Windows ty` -> `pass`
- `S08` `by:` `Terra 6.1 xhigh`
- `S09` `M` `src/cadrumo_runtime/host/tests/frontend/cli/portable_human_cli_runtime.py`
- `S09` `verify:` `export result surface parity owning module 3 cases plus human expiry deadline control 1 case` -> `pass`
- `S09` `verify:` `three additional M303 export parity and refusal cases after clock fix` -> `pass`
- `S09` `verify:` `fixture Ruff format and Windows ty` -> `pass`
- `S09` `by:` `Sol 6.1 high`

## Notes

- `S02` Generated metadata was adopted by concurrent commit 29d0663d16; no foreign metadata hunks restaged.
- `S03` Production mapping and bulk test adopted by concurrent commit b6e52594fb alongside foreign output-root feature; checkpoint retains remaining test delta.
- `S04` Existing worker-loss writer thread warning `CONNECTION_CLOSED` retained in test evidence.
- `S05` Reader source adopted by concurrent commit b9003df9be with foreign calendar/staleness changes preserved; authored patch and receipt retain attribution.
- `S05` S05 source already present in b9003df9be; separate remaining test checkpoint follows after concurrent Git lock delayed S04 staging.
- `S06` Intermediate 21/22 and 57/58 durable failures were investigated with preimage controls. One-line test readiness signal moved after custody fixture entry; assertions and production session policy unchanged. Final combined 58 passed.
- `S07` Broad gate reproduced stale condition-ID assertion. Both refusal codes intentionally share the completion condition; exact expected refusal-evidence diagnostic replaces obsolete substring oracle. No production change.
- `S02` Independent final review found the newly added absolute test import contradicted the active relative-import rule. Corrected only that import spelling and sorted position; production and scanner controls unchanged.
- `S04` S04 checkpoint also adopted a concurrent foreign ViewDownstreamReader test-support import migration. Targeted postimage rerun passed26; relay/helper/admission hashes unchanged during rerun. Existing worker-loss background thread `runtime_connection_closed` warning remained visible.
- `S08` Original failure was only the stale first-line text prefix. Expected full categorized line is independently grounded in English locale and registered REFUSED rendering; preceding ordinary notices remain allowed. PDB was diagnostic only, not passing evidence. All typed verdict, no-model-run, settlement, exit and no-desktop assertions preserved.
- `S09` Original five export failures stopped at CLI `session_expired` before intended assertions: login thread read real time while test proof used frozen time. Existing public `wall_clock` port now reads captured context through a fresh copy per call. Production authentication thresholds and expiry logic unchanged; explicit `SESSION_EXPIRED` negative control passed. A separate acquisition fixture failure in the four-node probe remains separately triaged.
