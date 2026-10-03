---
tags:
  - '#audit'
  - '#application-core-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:08d1d4412edc645d9ede67c898c9ad0a29dff3d72cfc0b73a68043f7896b9e7f'
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

### executable-admission | medium | Corrected library and fat-container acceptance

Independent review of the S07/S09 library-owned continuation found shared libraries admitted as executables and Mach-O fat wrappers checked only through their selected slice. Corrected: dynamic objects are limited to ELF with nonzero entry points; fat containers require Mach-O expectations. Tests exercise native PE/ELF executables, wrong CPU/container/digest, malformed bytes, synthetic Mach-O executables/dylibs and fat slices. These are bounded header checks, not loader-dependency or deployment-floor proof. No new production defect remained in corrective review.

### probe-lifecycle | medium | Live execution exposed and corrected missing stdin EOF

The first live CPython probe timed out because async shutdown did not close the stdin handle. Explicit handle disposal fixes EOF delivery; the regression uses a real child that reads to EOF. Tests cover output bounds, unsuccessful exit, timeout and cancellation; a real OS-lock handshake verifies the cancelled immediate child releases its resources. The next live attempt failed with an incomplete test environment; projecting disposable home/cache/temp paths fixed it. Production callers still own the complete immutable environment. stderr is bounded and not exposed. Descendant containment, dropped-future reaping guarantees, preflight I/O deadlines and hostile same-user filesystem races are outside these claims.

### python-browser-integration | low | Live development interpreter delegates browser policy to Python

The Rust probe calls existing Python optional-extra and browser provisioning owners through fixed embedded source, using isolated interpreter flags and JSON over bounded pipes. CPython 3.13.11 in the Windows development environment passed live identity checks, wrong-version/missing-distribution refusals, and returned MissingBuilds with both canonical Chromium requirements. No browser/driver is started and no component is downloaded. Exact release interpreter/distribution expectations can be projected from the assembler manifest. Windows library tests (29), Linux x64 tests (31), Clippy on both hosts, Windows Release compilation and Ruff checks passed. Tests using synthetic Mach-O bytes do not establish macOS execution. S07 platform projection, S09 acquisition and four-target acceptance remain PENDING.

### package-immutability-assertion | low | Retain original manifest for post-probe validation

Corrective review found the initial live acceptance test reread the manifest after execution, which could permit a self-consistent manifest/payload rewrite. The test now compares the original manifest bytes and reuses its original inventory for post-probe checks. The isolated Release archive copy is pinned by SHA256 be4eaf81eb2b254d2d535db69609efbe684bca9c790d0994609268fb39923b0b; source/copy/source hashes matched before extraction. The copy is relocated under this session's build tree into a path containing spaces and Unicode. This is artifact-specific evidence and does not declare the concurrent packaging owner's handoff complete.

### final-probe-acceptance | low | Relocated Release cohort and original inventory both pass

Final optimized Windows acceptance passed against the pinned archive copy: CPython 3.13.11 matched all 80 manifest distribution versions, reported MissingDependency for Playwright, and left the original manifest bytes and original file inventory unchanged. The explicit browser cache remained absent. The final development-interpreter probe also passed with MissingBuilds and both canonical requirements. Commands: cargo test --locked --release --features live-package-tests --test live_package and cargo test --locked --release --features live-python-tests --test live_python, each with the owning fixture environment. Required fixture paths and expectations are documented by the tests; selected live features fail if prerequisites are absent. Windows Clippy with all targets/features, formatting, Ruff and optimized library build passed after the corrections. The stricter package run completed in 229.62 seconds; this is acceptance evidence, not a performance benchmark. Verdict: PASS for this bounded library/probe checkpoint; overall S07/S09/S11 remain PENDING for their outstanding integration requirements.

## Recommendations

Retain the isolated library ownership and reuse this passing evidence while source/dependencies remain unchanged. S01/S10 integrate canonical projections and assembler metadata; S09 must satisfy both browser builds required by `src/cadrumo/application/provisioning_browser.py`. S11 owns the four-target package, execution and write-containment proofs. Do not promote broader application support from these standalone checks.
