---
tags:
  - '#reference'
  - '#native-build-confinement'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:0fbbd2bee3ae2f3b4072c1ff7af2cc4d2f1e4937f22c1240f5bd2a8300974a66'
related:
  - "[[2026-10-16-native-build-confinement-plan]]"
---

# `native-build-confinement` reference: `writer census`

## Summary

Static writer census of all non-test Python modules under `dev/packaging/native`, their embedded probe programs, CMake callers and just entry points on 2026-10-16. Three gpt-6-luna agents at max reasoning audited uv, Python writers and CMake independently. Semantic discovery used vaultspec-rag and vaultspec-core search, followed by whole-file reads and an AST census of filesystem call sites. The working tree changed concurrently; this report describes the final inspected implementation, not a historical commit or a complete dynamic filesystem trace.

The owner-directed invariant applies to repository-controlled build outputs and scratch. Normal uv, Cargo and npm machine caches remain owned by those installed tools; Cadrumo no longer configures uv cache, interpreter, tool or tool-bin directories. Test bootstrap also leaves ambient XDG/tool-home variables untouched so generic XDG configuration cannot indirectly create a private uv cache. An explicit developer setup, source-authoring command or installation operation is a different effect from building. Existing generated trees and caches were not deleted.

## Escapes and dispositions

| Site | Original effect | Classification and disposition |
| --- | --- | --- |
| `justfile:34`; `src/cadrumo/core/storage_environment.py:656` | Tool cache/home overrides redirected uv, Cargo, npm and Python under application storage; a second release-builder uv environment was synchronized | Superfluous custom tool management. Removed uv declarations and recipe/bootstrap overrides; use the installed system uv and preprovisioned interpreter. Application storage retains its own owner. |
| `native/cmake/Bootstrap.cmake:4` | Configure previously ran uv sync into a private builder | Superfluous build-time environment. Concurrent implementation now selects an existing interpreter and validates prerequisites without installation. |
| `dev/packaging/native/build_directory.py` | Direct writer CLIs accepted arbitrary --build or destination paths despite CMake enrollment | Erroneous boundary. Shared admission now binds visible presets, physical roots, source/cache/manifest agreement and declared output children before any CLI write. Configure-time generators use the same ownership map before the CMake cache exists. |
| `CMakeLists.txt:7`; `native/cmake/BinaryDirectory.cmake:6` | tmp creation before canonical guard; lexical-only admission could pass linked build roots | Erroneous boundary. Enrolled-directory admission now precedes the project-owned mkdir and refuses redirected physical roots. CMake itself can initialize its own configure bookkeeping before project code executes. |
| `native/desktop/CMakeLists.txt:67`; `native/desktop/scripts/frontend-install.mjs:266` | A build installed/deleted source node_modules and wrote a checkout lock | Legitimate developer prerequisite, erroneous build mutation. Build target now checks installed packages read-only; cleanup retains external prerequisites. Explicit npm setup remains available. |
| `dev/packaging/native/docs_build.py:150` | Shared documentation cache used dev_cache_dir under var/storage | Legitimate reuse with erroneous placement. Cache and receipt now live below the selected user_docs_work target. No cross-preset cache is written. |
| `dev/packaging/native/docs_build.py:58` | Documentation subprocess/index imports could create product, cache and temporary data using ambient defaults | Build scratch. Compile/index environment pins storage, derived caches and temp below the documentation targets. |
| `dev/packaging/native/authority_build.py:18`; `native/cmake/Authority.cmake:4` | Missing/stale authority triggered compilation/publication into checkout .authority | Legitimate authoring, erroneous implicit build effect. Native builds validate existing currency and refuse missing/stale authority; explicit just registry-publish-authority provisions it separately. Rebuild target refuses source authoring. |
| `dev/packaging/native/agent.py:149`; `native/cmake/Agent.cmake:45` | uv compile overwrote committed native/agent target lock | Legitimate authoring moved to candidate output. Build writes testing/agent-lock/target/requirements.txt and validates that candidate; promotion remains explicit source review. |
| `native/cmake/Docs.cmake:87` | Transcript refresh rewrote committed documentation during a CMake target | Source authoring. CMake refresh refuses; explicit just docs-generate-sequences remains the source-writing command. Checks use build-owned cache, logs and scratch. |
| `dev/packaging/native/environment_facts.py:276`; `environment_conformance.py:498` | Installed probe used default OS temporary directory | Temporary verification fixture. Parent supplies an explicit build-owned scratch root; the packaged interpreter cannot rely on inherited TEMP because launch policy can replace it. |
| `dev/packaging/native/launch_guard_check.py:16` | Launch admission created an OS-temp installation fixture | Temporary verification fixture, now explicitly build-owned. |
| `dev/packaging/native/package_launch_smoke.py:241` | Health probe used retained OS-temp storage and failure JSON | Temporary scratch with diagnostic retention; build-owned work is required and success cleanup remains bounded. |
| `dev/packaging/native/platforms/windows_verify.py:270`; `verification_paths.py:28` | Standalone verifier defaulted to development storage; absolute destination could escape the checkout | Verification output, erroneous fallback/escape. Require the owning build and keep extraction, hostile cwd, probe TEMP and evidence beneath it. |
| `dev/packaging/native/platforms/windows_trace.ps1:1`; `windows_trace_analysis.py:53` | Trace defaulted to storage development/build/native and accepted external absolute output | Verification evidence. Trace owns explicit build testing/traces output; analyzer admits the trace beneath the selected owner. |
| `native/desktop/scripts/build-paths.mjs`; `scripts/tauri.mjs`; desktop PowerShell wrappers | Direct desktop callers could use external build roots, inherit Cargo output overrides, or copy a kit before admission | Erroneous output/scratch placement. Admit root and standalone desktop presets against source/cache/manifest, force declared desktop_cargo, admit PowerShell build/output roots before creation or kit copy. |
| `native/cmake/BuildPaths.cmake`; `native/cmake/CTestEnvironment.cmake` | Linked declared children could redirect configure writes; native test fixtures inherited OS temp and product storage | Erroneous boundary and build-test scratch. Validate physical children before manifest/configure writes; root CTest and desktop/direct-backend tests pin temp and storage under the selected build, preserving more specific test-owned roots. |
| `packaging/authority/hatch_build.py` | Ordinary wheel/sdist builds could publish missing checkout .authority | Implicit source authoring refused for ordinary artifacts. Explicit editable environment setup retains its bootstrap; existing and embedded authority remains readable. |
| `justfile`; `dev/packaging/python_cohort.py`; `release_cohort.py`; release workflow | General distribution/cohort products and associated snapshots/archives/staging used var or checkout-root artifact paths | Build output and scratch. Migrated associated paths beneath build with active-owner cleanup protection; focused release-path checks are tracked in the ledger. |
| `native/cmake/Packaging.cmake:300` | CTest's pytest lifecycle lane inherited var-based logs/cache/scratch | Verification scratch. Test properties now explicitly bind test storage, logs, caches and scratch beneath testing for the chosen configuration. |

## File-by-file writer ownership

All paths below are relative to `dev/packaging/native/`. Build paths come from `build-paths.json`, whose children are validated against linked members and traversal. A low-level filesystem helper taking a destination is not an installation authorization; its build caller supplies the owning path. Read-only open calls and string replace calls were excluded from the writer inventory after inspection.

| Module and locator | Writes or delegated effects | Decision |
| --- | --- | --- |
| `action_cache.py:75` | Build action locks and completed inventory receipts | Legitimate build metadata; retain. |
| `agent.py:71` | Agent wheel under inputs/agent, source snapshot/build backend outputs, receipt; candidate lock under testing | Legitimate build products/candidate; retain system uv. |
| `agent_runtime.py:88` | Sibling transactional temporary runtime, Node archive download/extraction, npm workspace, runtime receipt | Legitimate build dependency and bounded scratch beside its output; retain. |
| `archive.py:41` | Contained archive member extraction to supplied build destination | Legitimate build extraction; retain. |
| `artifact_verify.py:44` | Fresh relocated ZIP tree, artifact locator checks, integrity evidence | Legitimate verification outputs; retain. |
| `assemble.py:123` | Staged package directories, copied Python/native assets, manifests, bytecode/archive generation, image resources | Legitimate staged build output; retain. |
| `assembly_transaction.py:52` | Candidate/rollback sibling trees and target package commit/recovery | Legitimate transactional scratch below staging owner; retain. |
| `authority_build.py:18` | No publication after correction; reads selected publication and currency | Read-only build admission; source publication stays explicit. |
| `build_timing.py:27` | Timing receipt directories and JSON | Legitimate build diagnostic metadata; retain. |
| `build_toolchain.py:79` | Selected SDK inventory and inputs sidecars supplied by CMake | Legitimate generated build evidence; retain. |
| `cached_command.py:106` | Removes stale output marker, writes checked command receipt | Legitimate build cache metadata; retain. |
| `cleanup.py:48` | Removes admitted build output groups only | Legitimate bounded build cleanup; retain. |
| `cmake_build.py:87` | Producer-owned output resets/reuse, Cargo invalidation receipt, command TEMP, dependencies/product/agent/stage results | Legitimate orchestration below selected binary; concurrent incrementality changes preserved. |
| `distribution_prepare.py:25` | Scratch package verification, package metadata, transactional icon/output publication | Legitimate distribution build output/scratch; retain. |
| `docs_build.py:58` | Compiled HTML/index, build/work site cache, log, scratch storage, completion markers | Legitimate documentation build; corrected ownership above. |
| `docs_stage.py:494` | Shippable documentation copy, inventory and stage manifest | Legitimate stage output; retain. |
| `environment_conformance.py:498` | Probe scratch parent and diagnostic stdout | Temporary verification scratch; explicit owner. |
| `environment_facts.py:188` | Probe generated configuration/storage and diagnostic stdout | Temporary verification fixture under supplied scratch. |
| `generate.py:318` | Generated C, Rust and JSON contract sources | Legitimate generated build inputs; retain. |
| `identity.py:107` | Identity JSON/CMake projection | Legitimate configure-generated build inputs; retain. |
| `installation.py:79` | Build installation-layout stage, metadata, icons, retained receipts, transaction candidates; explicit development install/remove prefixes | Stage/receipts are build output; external prefix effects are explicit installation operations, not ordinary build actions. |
| `installation_reuse.py:16` | Private stage/metadata candidate, copied or hardlinked unchanged build assets, backup/rollback trees and publication | Legitimate transactional installation-layout build output, bounded by installation_work and admitted stage/metadata roots; concurrent implementation retained. |
| `installation_filesystem.py:65` | Exclusive installation locks and hash-owned removals | Legitimate explicit installation lifecycle; retain caller ownership checks. |
| `launch_guard_check.py:21` | Fake installation marker, manifest, copied native host | Temporary build verification fixture. |
| `linux_desktop_runtime.py:143` | Build-installed Linux runtime provider closure and receipt | Legitimate dependency/staging output; retain. |
| `linux_manager_probe.py:154` | Diagnostic stdout; opted-in systemd user unit/service state through subprocesses | Explicit native acceptance probe, not ordinary filesystem assembly. |
| `linux_packages.py:39` | Atomic Debian/RPM metadata, output package, kit/locator; adjacent named temp files | Legitimate packages target and bounded scratch; retain. |
| `metadata.py:32` | Native version/image metadata and resource sources | Legitimate generated build metadata; retain. |
| `package_launch_smoke.py:244` | Health workspace, retained failure evidence, explicit probe directory/captured stdout | Build verification scratch/evidence. |
| `platforms/linux.py:37` | Linux binary relocation/loader metadata through platform tools | Legitimate staging modifications; retain. |
| `platforms/macos.py:86` | Mach-O header patches, install-name rewriting and codesign staged images | Legitimate staging/sealing output; retain. |
| `platforms/posix.py:60` | SDK archive/partial download, extraction, external probe script, staged runtime/assets, relocated package, hostile-loader fixtures, verification JSON | Legitimate dependency, stage and verification outputs with local scratch. |
| `platforms/windows.py:52` | Staged DLL/package relocation, native resources, SDK ZIP extraction and provenance | Legitimate build input/staging output; retain. |
| `platforms/windows_trace.ps1:1` | ETL capture, selected events, process JSON and trace summary; WPR/tracerpt OS state | Explicit trace evidence under testing/traces; privileged OS tracing remains operator invoked. |
| `platforms/windows_trace_analysis.py:64` | Validated trace summary JSON | Legitimate verification evidence under trace owner. |
| `platforms/windows_verify.py:283` | Package extraction, hostile cwd/modules, probe storage/temp, controlled runtime damage/restore, JSON evidence | Legitimate destructive fixture testing of an isolated extraction; owned verification root required. |
| `product.py:187` | Isolated source snapshot, authority pair staged inside snapshot, wheels, wheel inventories and installed dependency target | Legitimate product build output; system uv tool/cache policy, no custom environment. |
| `provision.py:57` | SDK acquisition delegation, requirements, runtime dependency target, provenance | Legitimate build dependency output; retain. |
| `service_descriptors.py:84` | Generated host/service descriptors | Legitimate generated build inputs; retain. |
| `stable_output.py:9` | Byte-preserving generated file replacement | Legitimate low-level build output primitive; retain. |
| `stdlib.py:43` | Explicit .pyc files and python.zip under supplied staging/build root | Legitimate packaged interpreter output; retain. |
| `update_agent.py:123` | Targeted staged agent updates, package inventory/provenance changes | Explicit build-stage maintenance; retain. |
| `update_images.py:32` | Atomic native image replacement and updated inventory | Explicit build-stage maintenance; retain. |
| `verify.py:18` | Selects build-owned verifier root, dispatches platform backend | Legitimate verification entry; no storage fallback. |
| `windows_msi.py:637` | Authored WiX source/build descriptor; explicit native maintenance runner invocations | Build source generation is package output; installation/removal/unregistration require explicit maintenance intent. |
| `windows_msi_build.py:143` | Compilation temp tree, MSI products, compiled receipt, public kit publication | Legitimate packages target and bounded scratch; retain. |

`build_directory.py` performs read-only CLI ownership admission. Other modules in the folder declare contracts, select paths/tools, inspect evidence or dispatch to these owners. `application_environment.py`, `linux_autostart.py`, `target.py` and `windows_msi_single.py` contain string replace calls, not filesystem replace calls. `docs_input_identity.py`, `hashing.py` and `linux_cxx_abi.py` open read-only inputs. Platform launch/probe strings were inspected separately from the AST census so embedded writes are included above.

## Associated build entry points

`native/cmake/BuildPaths.cmake:10` owns inputs/runtime, inputs/python-sdk, inputs/build-tools, inputs/agent, product, generated, bin, lib, symbols, cargo, stage, packages, testing, verification, desktop and user-docs children. Root, desktop and distribution presets enroll their respective repo-root build/preset directories. Generated CMake inputs/specs, sysroot inventories, CPack locators, Rust target directories, frontend bundles/generated content/results, docs stages and installation-layout metadata use those declared owners. `cmake --install` with an explicit prefix and native install/remove targets intentionally change the selected installation; they are not dependency acquisition or scratch outputs.

Related Python build helpers use `dev/packaging/build_storage.py` to bind application state, logs, bytecode policy, caches and temporary work beneath admitted build directories, restoring caller state afterwards. This helper never sets UV cache/install/tool/project-environment locations, XDG homes, Cargo/npm homes or a Python tool-cache prefix. Release clean-child output is admitted inside its own snapshot build tree and then published by its parent. Snapshot cleanup does not treat a dead parent as proof that every child has exited; orphan snapshots are reported and retained for manual review. The release workflow suppresses automatic source bytecode before Python starts.

Direct verification entry points now require the owning build, including normal and health launch smoke, installed environment probes, Windows trace analysis and standalone package verification. Assembly's CLI additionally binds its native image input and destination to the selected binary owner. Output-only identity, contract generation, metadata, product, provision, sysroot inventory and Linux runtime commands require a destination under an admitted declared output. Agent lock target names are validated before candidate directory construction.

The former orphan `native/cmake/CleanBuilder.cmake` private-environment remover has been removed. Custom tool management must not be restored. External uv-generated installation metadata such as uv_cache.json is standard uv-owned metadata in a build dependency target, not a repository uv-cache generator.

The target helper `uv_environment` only carries the target macOS deployment floor; it creates no uv environment or cache. The general release builder's normal system `uv run --isolated --frozen` fallback uses uv-owned isolation for the pinned release closure; it declares no private repository environment or cache root. Disposable uv venvs in non-native installation smoke tests are legitimate isolated acceptance fixtures using the system binary, not release-builder environment provisioning. Source-input publication and explicit installation remain separate operator effects.

## Verification limits

This is exhaustive static classification of the scoped module effects and inspected build call graph. It does not claim a full native bundle rebuild, privileged OS file trace, or prevention of arbitrary writes by external compilers/package hooks. Source changes made by another session after inspection require renewed verification. Existing var and external cache contents were preserved; moving code defaults does not reclaim historical files.

Direct development pytest invocations retain the project's configured test-log/storage policy unless the operator supplies build-owned roots. Some audit commands consequently wrote their own runner logs to var/storage; these are recorded separately from CMake-controlled build/CTest writers. CMake steps now explicitly bind test environments. Path admission is checked before operations, not an OS sandbox against concurrent link replacement or arbitrary external tool hooks.
