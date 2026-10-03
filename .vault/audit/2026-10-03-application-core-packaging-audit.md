---
tags:
  - '#audit'
  - '#application-core-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:a5e83aaf1f78b82463852578384d0d5e95eec8b5e8c08bbd942289cd050fb804'
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

### cmake-application-integration | low | Shared Cargo invocation preserves layout and runtime ownership

S10 review covers native/cmake/Rust.cmake, both Rust build consumers, the bundle/verify graph, CTest package verification and native/CONTRACT.md. The application crate now builds under the selected CMake binary directory and configuration with the same platform-projected compiler/linker environment as the platform crate. Cargo owns application input freshness. The application rlib remains build-only because no delivered runtime consumer exists; it is not injected into the Python package or file manifest. CTest receives the selected layout's manifest location, platform and ABI; it does not validate those fields against values taken from the tested manifest itself. Package tests serialize inventory access with the Python smoke test. Review found no concrete graph/configuration defect; a low test-label mismatch between staged and relocated inputs was corrected. Debug builds of both crates and application CTest pass; final Release graph/package verification is parent-owned and pending. Full S10 generated capability declarations and four-target acceptance remain open.

### fresh-python-product | low | Current authority source blocks the clean Release bundle

The isolated CMake Release bundle build passed dependency provisioning and Rust application compilation, then failed inside the existing Python authority wheel hook. The canonical registry compiler rejected unknown bindings in Modelo 232 revision 2016-2017. This is not recorded as successful fresh-package acceptance, and no registry validation was bypassed or source registry changed. The failing build directory is build/windows-x64/application-cmake; product/ready and a completed Release stage were not produced. Continue with the owning registry work to restore a valid source cohort before rerunning bundle/verify-package. The previously verified immutable Release ZIP remains a separate compatibility fixture only.

### selected-package-test | low | Artifact-specific CTest input is explicit

CADRUMO_APPLICATION_TEST_PACKAGE_ROOT defaults to the configuration's stage/app and optionally accepts an absolute independently extracted or installed package root. This allows the CMake-wired Rust compatibility test to exercise the prior verified Release artifact without implying the current source built successfully. The test receives canonical expected platform, ABI and manifest location from CMake. The test still requires an unchanged original inventory, exact Python/distribution versions and non-ready browser status against an absent disposable cache; optional fixture state assertions remain available. Release platform static/DLL/Rust consumers and application unit tests pass; the package test is in progress.

### cargo-native-toolchain | medium | Explicit C compiler projection also requires SDK headers

Final integration inspection identified Cargo C dependencies as another consumer of the selected toolchain. The Windows adapter now projects target-specific CC and AR alongside Rust compiler/doc tool, linker, static CRT flags and LIB. With CC pinned, standalone CTest exposed reliance on MSBuild's ambient INCLUDE: ring failed to find stddef.h even though the MSBuild build passed. Corrected by projecting the pinned MSVC and Windows SDK include directories through the same shared command. Both Release crates rebuilt successfully after this correction. Final independent review found no new concrete integration defect. Final Debug/Release CTest results remain parent-owned and will be recorded below.

### cmake-final-verification | low | Final Debug and Release CTest checks pass against their stated inputs

After explicit CC/AR/INCLUDE projection, both Rust crates build in Release; the Debug application CTest and all five selected Release CTests pass. Release covers platform static, DLL and Rust consumers, application Rust tests, and package compatibility against the pinned prior ZIP extraction. That package has no rlib, Cargo manifest or development packaging tooling in its inventory. Rust formatting and Clippy checks pass. Independent corrective review found no new integration defect. Verdict: PASS for the shared CMake/Cargo wiring and prior-artifact compatibility scope; fresh current-source bundle/ZIP acceptance remains PENDING because the existing authority compiler rejects the recorded registry bindings. S10 is not closed.

### cargo-reuse | low | Identical CMake builds reuse artifacts but CTest transitions can rebuild native dependencies

The first CMake build immediately after standalone CTest rebuilt ring and downstream crates, so its attempted unchanged-artifact assertion failed. Both invocations project the pinned tools and SDK paths, but Cargo also observes ambient MSBuild/CTest build-script environment differences. No fingerprint was bypassed. A subsequent identical CMake invocation completed Cargo in 0.11 seconds and preserved both the application rlib timestamp and SHA256. Reuse is demonstrated for repeated identical build invocations; optimal reuse across CTest/MSBuild environments is not claimed. Further normalization of non-toolchain build-script environment remains an improvement, not a passing performance claim.

### zip-probe-gate | low | Rust compatibility now participates in actual ZIP acceptance

Reviewed the CMake-generated argv projection, existing artifact verifier and new real-subprocess regressions. CMake remains the compiler/target/configuration owner; generated JSON preserves argument boundaries including Windows LIB lists. The artifact verifier supplies the extracted root rather than the staged-root cache setting, runs the fixed Rust test command after Python acceptance and refuses a passing result on failure. Reports distinguish passed application verification from standalone Python-only verification where it was not requested. The original archive and manifest hashes are rechecked before acceptance. Four artifact-identity tests pass, including probe rejection and manifest mutation; adjacent storage-contract checks remain passing. Ruff and CMake generation pass. Independent review found no concrete defect. Live combined verification is pending in build/windows-x64/application-cmake/archive-fixture, using the prior pinned ZIP rather than a freshly built package. The new fresh build attempt again failed the existing Modelo 232 registry bindings; no validation was bypassed.

### zip-probe-final | low | Combined Python and Rust verification passes on the pinned ZIP

The real artifact verifier passed existing Python relocation/native-library checks and the CMake-generated Rust command against one fresh extraction of the prior pinned Release ZIP. The Rust probe matched CPython 3.13.11 and all 80 distributions, returned MissingDependency for Playwright and preserved the original inventory. The result at build/windows-x64/application-cmake/archive-fixture/verification/Release/result.json records application_probe=passed with archive and manifest hashes. A final independent hash comparison confirms both original locator values. The final manifest-recheck assertion was added after the live process started; its failure behavior passed the real mutation regression and its success condition passed the post-run hash comparison. All changed Python files pass Ruff and formatting. Verdict: PASS for ZIP-bound probe integration; current-source package acceptance remains PENDING following the recorded authority compiler failure. Concurrent shared-branch commits captured the implementation; no merge history was rewritten.

## Recommendations

Retain the isolated library ownership and reuse this passing evidence while source/dependencies remain unchanged. S01/S10 integrate canonical projections and assembler metadata; S09 must satisfy both browser builds required by `src/cadrumo/application/provisioning_browser.py`. S11 owns the four-target package, execution and write-containment proofs. Do not promote broader application support from these standalone checks.
