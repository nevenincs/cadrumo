---
tags:
  - '#plan'
  - '#runtime-file-access-performance'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-04-application-distribution-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:f7097590a3c4fb377678a991eb5bad417352814221cb8b63afe91618222b3075'
---

# `runtime-file-access-performance` plan

## Description

Approved 2026-10-07

Authorization basis: the user requested action on performance findings, measurement of disk access, read counts and file types, and correction at the call-stack level before considering caching. Continue the runtime startup and repeated-call campaign. Existing accepted TUI, published registry authority and runtime-manager decisions govern operation contracts, digest-bound registry admission, generation freshness and process ownership. Equivalent call-stack corrections need no new ADR. Do not add caches until redundant work has been removed and measured; any subsequent cache must preserve its owning freshness and integrity scope.

This work owns new developer file-access diagnostics and bounded measured production corrections. Preserve concurrent Modelo, native-package, runtime-lifecycle and import-boundary work. The installed executable and current source are distinct measurement subjects; report which was measured.

The user additionally authorized rebuilding the binaries and benchmarking the build from start to finish on 2026-10-07. S04 uses the existing enrolled Windows Release build directory, preserving the separately retained older benchmark package. Include runtime, console, manager and desktop images, bundled documentation, ZIP packaging and native/artifact verification. Measure wall time and descendant process CPU; distinguish an incremental rebuild with managed caches from a clean build. Existing accepted interpreter-foundation, distribution and runtime-manager decisions govern this routine rebuild.

## Steps

- [x] `S01` - Measure runtime file access and attribute repeated opens to their callers; `dev/ci/runtime_file_access.py, dev/ci/tests/test_runtime_file_access.py, CLI-generated dev/quality/metadata/import_load_targets.dev.json and import_load_targets.json enrollment, plus ignored build/runtime-file-access measurements`.
- [x] `S02` - Remove measured redundant work at the owning call-stack boundaries; `local_observation_spreadsheet.py, inbound financial/providers/xlsx.py, inbound pdf/page_text_extraction.py, outbound calculation_summary_pdf/summary_container.py, calculation_review_xlsx_operation_composition.py, reconciliation_export_operation_composition.py and entrypoints/tests/test_operation_registry_imports.py`.
- [ ] `S04` - Rebuild the Windows runtime, manager and desktop binaries and benchmark the complete build pipeline; `Owning native/package build commands, isolated ignored build output, process-tree build measurements and rebuilt executable startup/error verification`.
- [ ] `S03` - Compare source and executable file access and review justified cache opportunities; `Fresh-process measurements, configured checks and the runtime-file-access-performance audit and ledger`.

## Parallelization

Execute sequentially in this workstream. Do not change another workstream's plan, profiler outputs or staged files.

## Verification

Validate diagnostic accounting with real temporary files and independently authored Windows event fixtures. Retain successful reads, unsuccessful opens, transferred bytes and extension totals separately. Correlate target process IDs with Python caller traces, exclude recorder output from counts and label the distinction between file API activity and physical media reads. Run focused production regression tests and configured format, style, type and import checks. Compare equivalent fresh-process workloads before and after each production correction. Review the integrated change and record remaining opportunities only after call-stack fixes.

Run the owning native bundle, CTest, ZIP and extracted-artifact verification recipes. Record per-stage and total timings, the build source fingerprint and cache conditions. Measure actual delivered runtime help and malformed-command exits, then verify runtime readiness and cleanup against isolated storage through the existing packaged probe. Retain no process-environment records.
