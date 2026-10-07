---
tags:
  - '#audit'
  - '#cmake-incremental-build'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:13a13bcb01fff1bca327199e1f064660ac3e2fc8898b76db47c5ad1585c2c846'
related:
  - "[[2026-10-07-cmake-incremental-build-plan]]"
---

# `cmake-incremental-build` audit: CMake incremental build and packaging

## Scope

Integrated uncommitted S01-S04 changes in the shared Windows worktree, governed by the accepted interpreter foundation CMake amendment. Review covers target prerequisites, producer input/output currency, separate native artifacts, bounded cleanup, bootstrap and install-based ZIP. Other concurrent application/documentation changes are outside this patch.

## Findings

### contract-inputs | high | Cached contract omitted a transitive default-language input

Initial review found `native/cmake/Contract.cmake` omitted `src/cadrumo/core/external_constants.py`, consumed through Settings defaults. The correction enrolls that file, interpreter bytes and dependency identity. Follow-up review confirms coverage of this concrete omission.

### cleanup-ownership | medium | Aggregate and installation clean targets silently had no outputs

Initial review identified python, python_d, frontend installation and builder cleanup gaps. Corrections enroll Python child binaries, explicitly lock and bound shared npm cleanup, and add CMake-owned builder removal with a regeneration sentinel. External interpreter ownership is reported explicitly. Isolated fixture tests pass; the shared installations were not destructively cleaned.

### icon-inputs | medium | Icon command edits could reuse stale outputs

The icon cache omitted `tauri.mjs`, which selects the generator invocation. The script is now an input. Focused Node tests and the frontend check command pass.

### assembly-inputs | medium | Windows assembly omitted its PE parser

`native/cmake/Packaging.cmake` now enrolls `platforms/pe.py`, imported by the Windows assembly owner. Follow-up review found the concrete omission corrected.

### compiler-granularity | low | Authority compiler currency remains conservative

CMake reuses the canonical compiler source-tree digest so transitive domain/schema changes cannot reuse stale authority. That existing owner intentionally enrolls broad core/domain/application/compiler trees and dependency manifests. Minimal invalidation within authority compilation is not established by this change. Stable downstream inventories prevent byte-identical publications from forcing unrelated package work.

### full-package-evidence | medium | Fresh full application ZIP acceptance is pending

The real package-release build passed frontend compilation and reached authority publication, then waited behind a documentation process already running before this task. The supervisor stopped only its own queued build and preserved the foreign process. No historical ZIP is accepted as current evidence. Standalone CPack fixtures pass, but full ZIP creation and extracted application verification must be completed after the shared documentation build is available.

### final-focused-verification | low | Corrected producers pass focused checks and native no-op proof

After all source fixes, 42 focused Python tests pass across cache currency, missing-output recovery, authority coverage, Cargo sibling stability, CMake input enrollment, clean/rebuild isolation, builder restoration and CPack refresh. All 17 changed Python files pass Ruff lint, formatting and ty. The frontend has 23 focused Node passes plus npm run check. Actual Windows CMake configure and separate static/shared/consumer/interpreter builds pass. A final unchanged build preserves exact timestamps for python.exe, cadrumo_platform.lib, cadrumo_platform.dll and platform-consumer.exe; evidence is `build/windows-x64/incremental-native-noop.json` and its log. Final Python logs are under `var/storage/development/.logs/test-runs/2026-10-07/20261007T082131.048125Z-pytest-45144-71c29ea8` (13 tests) and `20261007T082350.759162Z-pytest-88384-9d248cba` (29 tests). Linux/macOS native release acceptance was not run on this Windows host.

Independent follow-up review confirms the four concrete defects corrected and no additional blocking defect. Verdict remains PENDING for full application ZIP acceptance and the reported repository-wide type-check baseline. S01-S03 are implemented and checkpointed; S04 remains open. Minimal compiler invalidation is not claimed for the documented conservative authority policy.

## Recommendations

Verdict: PENDING verification. Independent follow-up review confirms all four reported code defects corrected and found no additional blocking defect in the changed interactions. Finish final native/type checks and the full application package/verify-package run before claiming complete pipeline acceptance. Relevant evidence: 23 Node tests and npm run check pass; just check-style and check-format pass; 13 final cleanup/cache/distribution fixture tests pass. Earlier combined native Python suite passed 37 tests. Global type check initially reported five in-scope diagnostics (corrected with focused type evidence) and two concurrent registry schema diagnostics. Final evidence will be appended rather than replacing these findings.
