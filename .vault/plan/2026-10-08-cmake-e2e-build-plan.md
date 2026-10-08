---
tags:
  - '#plan'
  - '#cmake-e2e-build'
date: '2026-10-08'
tier: L1
related:
  - '[[2026-07-13-docs-cli-sequences-adr]]'
  - '[[2026-09-29-docs-build-workflow-adr]]'
  - '[[2026-10-04-application-distribution-adr]]'
modified: '2026-10-08'
body_schema: body-v2
body_hash: 'sha256:1ed99b4dbfaa68742db3e957e307ec08a2d0abe4e145c2c02771b27a0ee7822f'
---

# `cmake-e2e-build` plan

## Description

Approved 2026-10-08

The user authorized clearing build and scratch outputs and completing a CMake-driven build until cadrumo.exe executes. Cleanup and initial configuration completed. The first release build stopped at stale documentation transcripts and transient sequence execution failures; a focused filing-spine refresh now passes all 13 sequences. Preserve unrelated concurrent changes.

S01 follows the linked documentation sequence and build decisions for explicit owner-driven refresh, reviewed golden changes, and the mandatory release gate. The packaging decision governs the canonical staged executable and release verification. These are routine repairs within accepted decisions; no new costly choice is required. Build products stay under the preset binary directory.

The 23 affected documentation pages were rerun through explicit CMake maintenance targets. Every execution expectation passed except the Modelo 390 inspection's stale formula count. Registry commit c2f1160b9e added seven declared formulas to the 19-formula baseline; the contract now expects 26 and its focused CMake refresh passed. The other four Modelo 390 sequences passed. Reviewed golden changes preserve exit/status outcomes and export payload hashes and sizes; changes cover current registry revisions, identifiers, provenance, and the explicit login recovery action after logout. Maintenance selectors were cleared and verify-release restarted. Its native libraries, manager and four product wheels rebuilt successfully. Documentation waited from 12:02 until about 13:11 Madrid time on the shared site-cache lock held by a concurrent windows-installers-x64 compile whose source snapshot predated the assertion repair. The lock cleared and the corrected strict documentation compile is now executing its live sequence gate. Its immutable source snapshot contains formula_count == 26. The user requested continuation after receiving the timing and build-graph diagnosis. The final release and executable checks remain pending.

The strict release documentation gate finished at 14:42 Madrid after 5445 seconds. All transcript comparisons passed, but two Modelo 390 executions failed: annual verification exceeded its command settlement wait, and supply-binding seed filing lost its runtime connection. The full release target exited 1 and has not produced executable acceptance. A focused CMake check of modelo-390-annual-2025 is running before another release attempt. Verification now separates its existing 60-second transport budget from a 1800-second settlement budget, following the existing calculation client pattern; this does not retry or waive any outcome. The isolated annual sequence passed with the original CLI already loaded. The complete Modelo 390 page check passed with the settlement fix, including supply-binding filing. CMake configuration also exposed that desktop-headless-test had neither an assembled-package dependency nor a default package root in the full source build. The full build now derives that root from the canonical stage directory and makes the launch test depend on bundle. Generated Release project evidence confirms the stage/Release/app path and bundle dependency. desktop-headless-test is running; its documentation producer currently waits for the shared cache lock held by the separate windows-installers-x64 strict compile started at 14:42. User approval to interrupt that separate compile has been requested asynchronously. No executable launch has yet completed.

## Steps

The 18:19 build was stopped after five enrolled Python sources changed during compilation; the documentation input-stability guard would correctly reject it. Reconfigured the existing CMake-owned product source snapshot at `build/windows-x64/product/build/source` with its standard `windows-x64` preset and shared documentation cache disabled. This snapshot contains the staged published authority and the code used for the product wheels. Its standard preset owns all nested output paths. Configuration passed; session 64610 runs `desktop-headless-test` with the Session 0 check enabled. Publisher build credentials are inherited in memory through the existing settings owner without printing or copying them. The separate installer build remains untouched. Do not rebuild the parent `python_product` while this snapshot is the active source tree.

Latest authorization: the user requested ensuring the package is built for launch testing. Resumed the package-and-Session-0 check through desktop-headless-test. Implemented CADRUMO_DOCS_SHARED_CACHE (default ON), configured this preset OFF to avoid cross-configuration cache contention, and retained strict compilation, all sequence assertions, authority/input validation and package verification. Added the CMake user_docs_driver_test target; all 13 tests pass, including local compilation without touching a busy shared cache and refusal of changed inputs. Ruff and whitespace checks pass. The restarted strict compile began at 18:19:31 and entered its live sequence gate at 18:23:25. Build session 73931 owns package assembly and the launch test with CADRUMO_TEST_HEADLESS_SESSION=1. Only the superseded owned build was stopped; the separate installer work remains untouched.

Stopped at the user's explicit request on 2026-10-08: the owned desktop-headless-test CMake process 30004 and its descendants were terminated. The separate windows-installers-x64 documentation compile 18600 was left running. The proposed shared-cache option was not implemented; only its scope dry-run was performed. Existing edits remain, S01 stays open, and cadrumo.exe has not been executed or accepted. Do not resume the build without a new user request.

- [ ] `S01` - Restore documentation verification through explicit CMake transcript maintenance, then build and execute the release package; `native/cmake/Docs.cmake, native/cmake/Packaging.cmake, native/desktop/CMakeLists.txt, native/CONTRACT.md, dev/packaging/native/docs_build.py, dev/packaging/native/tests/test_docs_shared_site.py, docs/_sequences, src/cadrumo/entrypoints/cli/runtime_modelo_verification.py, build/windows-x64`.

## Parallelization

One owner executes S01. A single CMake invocation may schedule independent documentation pages with parallelism two. Do not run competing builds in the same binary directory.

## Verification

On the user's subsequent launch-test request, confirmed the runner is in Windows Session 0 and executed `cmake --build --preset release --target desktop-run`. The actual executable started and returned exit 1 with `package_unavailable`, operation `environment`, `NotFound`, OS code 3. The CMake-derived `build/windows-x64/stage/Release/app` does not exist; its `data/package-manifest.json` and `python.exe` are therefore absent. This establishes native process execution, not successful application or headless CLI startup. No competing build was stopped and no package files were fabricated or copied manually.

The user subsequently requested building cadrumo.exe. Removed the unnecessary documentation dependency from desktop-host-build after confirming the Rust/Tauri compile consumes the frontend and generated native contract, while bundle still requires documentation. Configuration and `cmake --build --preset release --target desktop-host-build --parallel 4` passed, producing `build/windows-x64/cargo/desktop/release/cadrumo.exe`; Rust reported an optimized build in 1m 26s. The separate installer build was untouched. Packaged runtime assembly and successful executable launch remain unverified, so S01 stays open.

Review golden differences against documented expectations and current authority. Configure the windows-x64 preset, run user_docs_sequences_refresh for affected pages, then verify-release and desktop-headless-test through CMake. Check changed-file formatting and repository validation. Record the actual executable path and results; completion requires executable execution, not compilation alone. Perform one integrated final review.
