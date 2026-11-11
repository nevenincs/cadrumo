---
tags:
  - '#exec'
  - '#robust-logging'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:8293c32f3c82d34b34a0efbd7fae9b628ccd15ede013669c00151d0aa2720910'
related:
  - "[[2026-10-27-robust-logging-plan]]"
---

# `robust-logging` ledger

## Changes

- `S01` `A` `src/cadrumo/core/diagnostic_dispatch.py`
- `S01` `M` `src/cadrumo/core/logging.py`
- `S01` `M` `src/cadrumo/core/log_file_handler.py`
- `S01` `A` `src/cadrumo/core/tests/test_diagnostic_dispatch.py`
- `S01` `A` `src/cadrumo/core/tests/test_logging_dispatch.py`
- `S01` `M` `src/cadrumo/core/tests/test_diagnostic_log.py`
- `S01` `M` `src/cadrumo/core/tests/test_logging_first_record.py`
- `S01` `M` `src/cadrumo/core/tests/test_logging_rotation.py`
- `S01` `A` `dev/ci/logging_benchmark.py`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `scoped core logging pytest unit 100 tests` -> `pass`
- `S01` `verify:` `scoped ruff lint and format eleven Python paths` -> `pass`
- `S01` `verify:` `scoped ty eleven Python paths` -> `pass`
- `S01` `verify:` `normal benchmark 8000 records zero dropped or failed` -> `pass`
- `S01` `verify:` `slow and blocked benchmark with py-spy thread samples and handle churn` -> `pass`
- `S02` `A` `native/application/src/diagnostics/dispatch.rs`
- `S02` `M` `native/application/src/diagnostics/mod.rs`
- `S02` `M` `native/application/src/diagnostics/logging.rs`
- `S02` `M` `native/application/src/diagnostics/panic.rs`
- `S02` `M` `native/application/tests/diagnostics.rs`
- `S02` `M` `native/application/tests/panic_hook.rs`
- `S02` `M` `native/application/tests/helper_diagnostics.rs`
- `S02` `M` `native/application/tests/webview_diagnostics.rs`
- `S02` `M` `src/cadrumo_runtime/host/worker.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_profile_worker_operations.py`
- `S02` `verify:` `CMake-owned native application full suite with platform feature 337 passed plus real-child panic harness` -> `pass`
- `S02` `verify:` `native diagnostic saturation observer rotation and replay tests` -> `pass`
- `S02` `verify:` `worker operation integration 5 tests including blocked real file sink` -> `pass`
- `S02` `verify:` `scoped Python ruff format and ty` -> `pass`
- `S02` `verify:` `scoped rustfmt owned paths` -> `pass`
- `S02` `verify:` `CMake application.clippy final production state` -> `pass`
- `S03` `M` `src/cadrumo/core/logging.py`
- `S03` `M` `src/cadrumo/core/tests/test_logging_dispatch.py`
- `S03` `M` `src/cadrumo/core/tests/test_diagnostic_dispatch.py`
- `S03` `M` `src/cadrumo/core/tests/test_logging_first_record.py`
- `S03` `M` `dev/ci/logging_benchmark.py`
- `S03` `M` `.vault/research/2026-10-27-robust-logging-research.md`
- `S03` `M` `.vault/adr/2026-10-27-robust-logging-adr.md`
- `S03` `A` `.vault/audit/2026-10-27-robust-logging-audit.md`
- `S03` `verify:` `just check-code full aggregate` -> `pass`
- `S03` `verify:` `final local-storage full logging suite 102 tests` -> `pass`
- `S03` `verify:` `changed-path Ruff lint format and ty` -> `pass`
- `S03` `verify:` `normal slow blocked and large benchmark delivery and handle comparison` -> `pass`
- `S03` `verify:` `py-spy 8415 samples zero sampling errors and no producer sink/redaction frames` -> `pass`
- `S03` `verify:` `original 32-cycle real worker lease churn with ordinary logging enabled` -> `pass`
- `S03` `verify:` `just check-registry-gate validity and runtime-load` -> `pass`
- `S03` `verify:` `just check-registry-gate integrity stale publication` -> `fail`
- `S03` `verify:` `Y-volume logging stress reruns with metadata and rotation stalls` -> `fail`
- `S03` `verify:` `change-scoped test-gate fixed contract set 217 tests` -> `pass`
- `S03` `verify:` `test-gate final documentation harness stale authority two tests` -> `fail`
- `S03` `verify:` `32-writer 8000-record benchmark zero losses p99 64.3us` -> `pass`
- `S03` `verify:` `final Y-volume complete logging suite after competing global scan stopped 102 tests 16.15s` -> `pass`
- `S03` `M` `src/cadrumo/core/redaction/tax_identity_admission.py`
- `S03` `verify:` `blocked application authority diagnostic regression before correction` -> `fail`
- `S03` `verify:` `blocked application authority diagnostic regression after correction` -> `pass`
- `S03` `verify:` `opaque inspection and stdlib constructor callback regressions before correction` -> `fail`
- `S03` `verify:` `expanded core logging and redaction final 418 tests` -> `pass`
- `S03` `verify:` `post-isolation real worker operations integration 5 tests` -> `pass`
- `S03` `verify:` `post-isolation just check-code full aggregate` -> `pass`
- `S03` `verify:` `final just check-types all supported platforms after reflection annotations` -> `pass`
- `S03` `verify:` `final changed-path Ruff lint and format` -> `pass`
- `S03` `verify:` `normal32-writer large-record and60second blocked output benchmarks` -> `pass`
- `S03` `verify:` `new py-spy8789samples6392producer no sink/redaction no authorityframes` -> `pass`
- `S03` `verify:` `shared canonical publication registry validity runtime-load integrity generation1c28` -> `pass`
- `S03` `M` `src/cadrumo/core/observability/store.py`
- `S03` `M` `src/cadrumo/core/observability/tests`
- `S03` `verify:` `expanded logging/redaction 474 tests` -> `pass`
- `S03` `verify:` `full legacy observability 131 tests` -> `pass`
- `S03` `verify:` `Ruff lint format ty strict basedpyright` -> `pass`
- `S03` `verify:` `unread stderr configured and fallback normal process exit` -> `pass`
- `S03` `verify:` `32 producers 8000 records zero loss p99 90.9us 156 handles before and after100queue lifetimes` -> `pass`
- `S03` `verify:` `py-spy20Hz idle1309samples zero errors no producer sink redaction no authority frames` -> `pass`
- `S03` `verify:` `explicit basedpyright Windows Linux Darwin logging.py and store.py all zero errors` -> `pass`
- `S03` `verify:` `feature vault check all clean with safe markdown repairs` -> `pass`

## Notes

- `S02` One existing native live-runtime test intentionally ignored by its existing test annotation; native crate-wide fmt fails only in concurrently edited `person_operations.rs` outside this Step.
- `S03` Workspace Y storage intermittently stalls inside lstat and file rotation; daemon-only stack captured and identical final102 tests pass with unchanged finite timeouts on configured local C temporary storage. Failures retained in research. Registry publication belongs to calendar session; native global formatting issue belongs to `person_operations.rs` owner. Change-scoped test-gate still running fixed contract fallback.
- `S03` Implementation checkpoint committed with S03 open and integrated review PENDING only publication-dependent documentation verification. Calendar owner will publish after its running all-model parity assessment and rerun only the two failed sequence corpus checks; passing217 contract tests and4 worker-count harness tests need not be repeated. Debug rebuild cleared; source changes complete. Native crate-wide format retains unrelated `person_operations.rs` drift.
- `S03` Queued diagnostic redaction now uses context-only conservative lexical admission to avoid application authority locks. Technical identity lookalikes can hash in logs; domain/output admission stays unchanged. Snapshot and factory guards avoid metaclass and instance hooks before stdlib record construction. Full aggregate passed before final factory-body/type refinements; imports unchanged and fresh full type/Ruff plus final418 tests cover refinements. Python source quiet. Fresh docs corpus still requires expected golden refresh and quiet worker verification by calendar owner; S03 stays open.
- `S03` Committed56a77fa7e6. Buffered stderr lock reproduced process-exit freeze beyond20s; raw diagnostic stream and async default fallback repair it without changing CLI output buffering. Final identical expanded474 pass54.02s; full131 recording fixture tests pass11.62s after explicit serialization/drain and exception snapshot migration. Source quiet. No builds per user hold; S03 stays open for shared integration checks.
- `S03` Follow-upcb7d317b6d explicitly guards Unix-only `register_at_fork` from Windows type stubs. Existing hasattr already skipped that branch at runtime on Windows; source behavior unchanged. Explicit all-three-platform strict checks now pass, superseding default-platform-only proof. Full repository types retain unrelated active profile/wizard/runtime migration diagnostics; S03 remains open, no builds.
