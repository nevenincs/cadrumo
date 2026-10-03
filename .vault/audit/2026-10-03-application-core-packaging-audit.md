---
tags:
  - '#audit'
  - '#application-core-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:b3346fa6dfb49ec1c74bceac8663a0f9a5fa639fae21484c3d9502cb41a60be5'
related:
  - "[[2026-10-03-application-core-packaging-plan]]"
---
# `application-core-packaging` audit: `independent Rust application library`

## Scope

Read-only independent review of new `native/application/`, covering S06 and library-owned S07-S08 behavior. User clarification authorizes Rust work independently of the concurrent Python package session. The crate consumes target/path/environment inputs and the existing package inventory; shared Python, native/platform and CMake sources were untouched. Verdict: PASS for the standalone library scope subject to the pending integration coverage below; the complete continuation remains PENDING.

## Findings

### portable-paths | medium | Unix backslash aliases corrected

Initial review found filesystem inventories replacing every backslash with a separator, allowing a Unix filename alias to evade unexpected-file detection. Resolved: `src/value.rs` converts native components individually; package and component inspection now reject such filenames. The Unix regression exercises real files.

### content-identity | medium | Mirror rotation no longer invalidates identical bytes

Initial receipt comparison included transport URLs and admission limits. Resolved: immutable identity checks use component/revision/target/digest/archive size/executable fields; current size and entry limits are checked separately. A mirror-rotation regression proves reuse without opening a source.

### component-repair | medium | Damaged versions are retained while a new generation is activated

Initial provisioning could detect damage but could not repair an existing digest directory. Resolved: explicit provisioning selects a retained digest-generation directory, preserving existing consumer paths. Stored size-policy violations are incompatible content rather than unrecoverable acquisition failures. The oversized-file regression proves replacement through a new generation and retention of the damaged original.

### entry-count | low | Cached admission includes directory entries

Receipt entry count originally represented files only. Resolved: extraction records the full ZIP entry count; reuse and fresh acquisition enforce the same supplied maximum. The regression tightens the bound below an archive containing one directory and one file.

### integration-coverage | low | Packaged platform and browser acceptance remains pending

No high or critical findings remain after corrective review. Tests cover real filesystem/archive operations, concurrent writers, a killed child writer, stale staging, failed activation, cancellation, immutable child execution and package inspection. Windows x64 tests, Clippy, formatting and Release library build have passed; Linux x64 runs use the pinned Rust compiler in WSL, with final results recorded in the ledger. These are library checks, not glibc-floor or complete packaged-delivery evidence. Linux ARM64/macOS ARM64 execution, shared Settings/platform projections, trusted Chromium/headless-shell metadata and real HTTPS success/redirect/transport-interruption cases remain pending. Cooperative cancellation occurs between reads; a blocked read is bounded by transport timeout. The crate does not claim power-loss durability or protection against hostile same-user filesystem mutation.

### linux-shared-filesystem | low | WSL shared-drive run encountered a permission failure

The final 22-test Linux run on the Windows-mounted Y drive failed one initial component installation with `PermissionDenied` in the mirror-rotation test; 21 tests passed. The same test immediately passed in isolation without a source change. No failing assertion was weakened or suppressed. Root cause is unestablished; this is not reported as a clean shared-filesystem run. A separate full run uses an explicitly selected Linux-native binary/test directory below `/tmp/cadrumo-application.*/build/linux-x86-64/`; its locator and log are retained under the workspace's `build/linux-x86-64/application-core/`. The generated verification directory is independent of Python packaging. Filesystem errors remain surfaced to callers.

### final-library-verification | low | Native-filesystem Linux suite and Windows checks pass

Final unchanged-source verification passed: 20 Windows x64 integration tests, 22 Linux x64 integration tests on native Linux storage, Windows Clippy with warnings denied, formatting, and the optimized Windows Release library build. Both platforms executed the killed-writer recovery and real child-environment tests. Rust 1.96.0 was selected explicitly. The Linux output root is `/tmp/cadrumo-application.QsWHTMDZ/build/linux-x86-64/`; the retained log is `build/linux-x86-64/application-core/native-filesystem-tests.log`. The earlier shared-drive failure remains recorded above. S06's clarified standalone-library scope passes; S07-S11 integration/acceptance obligations remain open.

## Recommendations

Retain the isolated library ownership and reuse this passing evidence while source/dependencies remain unchanged. S01/S10 integrate canonical projections and assembler metadata; S09 must satisfy both browser builds required by `src/cadrumo/application/provisioning_browser.py`. S11 owns the four-target package, execution and write-containment proofs. Do not promote broader application support from these standalone checks.
