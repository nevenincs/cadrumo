---
tags:
  - '#audit'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:9a2b36d3268352719193f27b90e2f965d702dbdeb2a4684ad5b3a88a85f598be'
related:
  - "[[2026-10-03-application-packaging-plan]]"
---
# `application-packaging` audit: `Windows interpreter foundation`

## Scope

S01-S04 of the 2026-10-03 application-packaging plan, native sources and dev/packaging/native working-tree changes. Core Python settings/storage edits by concurrent work are excluded. Review follows the accepted narrow foundation ADR; the broader application ADR remains proposed. One executor owns builds and artifact checks; the native_review reviewer reused their evidence.

## Findings

### com-identity | high | Initial relocation omitted public COM extension aliases

Initial review: REVISION REQUIRED. Relocated win32comext extensions did not satisfy public win32com.shell imports. Corrective review: resolved by generated win32com aliases, with a passing win32com.shell.shell import from the relocated native subtree in the full artifact verifier.

### com-environment | high | Initial pywin32 bootstrap could select host registry paths

Initial review: REVISION REQUIRED. pywin32 SetupEnvironment could read host extension/build/cache paths. Corrective review: resolved by a checked package patch selecting bundled extensions and U/cache/pywin32/gen_py. Artifact verification asserts those paths and package immutability. No core storage defaults were changed by this work.

### acceptance-evidence | medium | Final OS write tracing and fresh product command remain pending

Corrective review verdict: PENDING, with no remaining high findings. Reused passing evidence covers C static/DLL and Rust ABI consumers, qualified native imports, PDF operations, child startup, Unicode/spaces, hostile environment and cwd, missing inputs, invalid Python PE, hostile/missing qpdf, ignored .pth and immutable package hashes. Ruff check, format and ty passed for all authored Python tooling. The exact product composition command is documented and its fresh run is in progress. Incomplete Process Monitor captures and a WPR capture with dropped events do not establish whole-process write containment. Python audit evidence is explicitly narrower.

### acceptance-closure | low | Fresh product and lossless authored trace pass

Final integrated verdict: PASS. The fresh provision command verified the pinned official SDK and installed 77 locked Windows dependencies. The documented product command built and installed all three matching 0.5.1 distributions, then assembly produced .artifacts/native/repeatable/package. Full verification against the outside-checkout Unicode/spaces installation passed; .artifacts/native/verification.json records the current run. The corrected native_review reviewer found no remaining high findings and approved the tracing implementation, conditional only on the authored trace command finishing. That command finished with exit zero: 2013 scoped parent/child events, four actual writes, zero events lost, and all observed mutations under U. Evidence is C:/Users/hello/cadrumo-native-proof/repeatable-trace/summary.json, application-events.jsonl and capture-summary.txt. The raw machine-wide capture was removed, and no owned recorder remains active. Review coverage is the interpreter foundation and exercised parent/child probe, not every future application workflow.

### concurrent-root-policy | high | Current source no longer matches the verified root mapping

Subsequent review: REVISION REQUIRED for the current working tree; the prior artifact baseline remains PASS for its scoped proof. Concurrent edits to native/platform/src/lib.rs replaced Known Folder discovery with repository/current-directory discovery and var/storage defaults. Secure storage now shares that root instead of U/data. These changes arrived after the tested native compilation, and some were present when the S02 checkpoint was staged. The tested original source is preserved under .artifacts/native/repeatable/product/source/native, with its original generator in that snapshot. Current-source review cannot reuse the binary's path/isolation result. No concurrent edits have been reverted. Reconcile the chosen policy and rebuild before closing S02/S03/S04.

### concurrent-override-policy | high | Current override allowlist conflicts with declarations and tests

Concurrent generate.py edits generate storage overrides that the changed Rust provider preserves. native/package-layout.json still declares an empty allowlist and verify.py expects inherited storage redirects to be rejected. This is an unresolved interface mismatch, not a finding against the other task's intended storage semantics. The user has been asked whether to incorporate that policy and rebuild or hand over the verified artifact while its owner completes the changes. Whole-plan completion and current-source approval remain open.

### cmake-shared-inputs | high | Configuration switching originally reset shared dependencies

Review found that Visual Studio tracks custom actions separately per configuration,
so Debug could dispatch provisioning after Release and delete the shared runtime.
Corrected with input fingerprints, output inventories and an OS lock around shared
writers. Focused checks pass for unchanged inputs, changed inputs, missing outputs
and a second process waiting for the first writer. Full configuration-switch
acceptance remains pending with the current artifact.

### cmake-product-inputs | high | Product incremental inputs omitted selected authority

Review found that the selected authority descriptor/database and root wheel metadata
were absent from the original dependency graph. Both now participate in CMake inputs
and content fingerprints. Transient publication locks/journals are excluded. The
fresh wheel attempt correctly refused a stale modelo 303/2022 form-layout digest;
the live checkout was subsequently verified current, and a new snapshot build is
running. No registry validation was bypassed.

### platform-ownership | high | Shared packaging originally embedded Windows assumptions

The user's correction required moving physical platform names and operations into
explicit backends. The shared layout now composes the Windows platform contract;
SDK acquisition, PE relocation, pywin32 patches, resources, C bootstrap and Windows
acceptance/trace tooling have explicit Windows owners. Shared assembly creates
contract-derived parents, supports sibling .pth paths, and passes explicit roots
to smoke tests. Platform contracts and the loader trigger CMake reconfiguration.
Corrective review reports no remaining high findings in that scope. Unsupported
Linux/macOS selections fail rather than using Windows defaults.

### storage-owner-reconciliation | low | Current generation follows the user-confirmed core owner

The accepted foundation amendment supersedes the earlier Known Folder and empty
allowlist policy. Native generation consumes Settings.storage_env_var_names and
canonical taxonomy defaults; the package layout no longer duplicates mutable
location declarations. The two existing native storage contract tests pass. This
resolves the prior decision/document mismatch; fresh artifact behavior still needs
the acceptance run before S02-S04 can close.

### current-cmake-evidence | medium | Final bundle checks remain pending

Current verdict: PENDING. Five explicit cleanup targets passed in an independent
configured build tree, preserving unrelated files and configuration and refusing
source cleanup. Ruff and ty pass. Current Release host/bridge compile; dumpbin
shows only api-ms-win-core-synch-l1-2-0, ntdll and KERNEL32 imports before main.
The banner prints CADRUMO 0.5.1, build 1761, UTC build date and CPython 3.13.11.
Earlier C static/DLL/Rust consumers passed; current full bundle, all native-module
imports, optional development executable, install/ZIP acceptance and renewed trace
remain owned by the executor and are not inferred from historical evidence.

### compiler-input-coverage | high | Wheel invalidation omitted authority compiler dependencies

Focused review traced the wheel hook into dev.registry, dev.corpus,
dev.docs.preprocess and dev.cache_root. These compiler families, their package
initializers, and source normalization/ignore rules now participate in the CMake
product inputs. Active .aeat-generated-export-transaction-* files are excluded
from both CMake inputs and source snapshots; they are publication coordination
state, not product source. A Debug snapshot attempt refused an actively locked
transaction file before this correction. No registry validation was bypassed.

### complete-native-imports | high | Broader smoke tests exposed two relocation defects

The current smoke test imports all 119 retained native identities, including the
20 SDK extensions. It exposed the unused Pillow Tk adapter after stdlib Tk pruning,
and axdebug's basename import of axscript.pyd. Explicit Pillow exclusions record
file hashes and reasons in the package manifest. A PE import-table reader now
enrolls basename-referenced PYDs alongside DLLs in native search and ambiguity
checks. Qualified PYDs retain absolute-path loading, allowing SQLAlchemy's distinct
engine/sql _util_cy extensions. Windows smoke prerequisites initialize win32ui
before dde. Corrective review found no blocking defects in these fixes.

### current-release-evidence | low | Current Release package and outside-checkout install pass

The current host embeds longPathAware; compiler scratch is preset-scoped beneath
the build tree. CPython 3.13.11, the three CADRUMO 0.5.1 wheels and 77 locked
third-party distributions assembled successfully. ctest --preset release passed
all four tests: packaged Python, C static, C DLL and Rust consumers. The package
test imports all 119 native identities and checks all 80 distributions. Standard
cmake --install produced Y:/code/cadrumo-native-proof/CADRUMO CMake á 漢字; its
full --check-package and packaged smoke test passed from an unrelated cwd.
Both native storage projection tests, Ruff and ty pass. Debug/ZIP acceptance is
still running. The renewed trace lost events during heavy filesystem activity and
is rejected as evidence; its raw capture was removed. The next trace uses a
Python executable filter and increased buffers. Current overall verdict remains
PENDING until those required checks pass.

### native-source-manifest | high | Global ignore rules omitted a required CMake source

Resume review found that the authored Windows long-path manifest was hidden by
the global `*.manifest` ignore rule. A clean checkout or source snapshot would
omit a required native build input. Resolved with a path-specific exception in
`.gitignore`. The real `dev.source_tree.repository_files` enumerator now includes
the manifest and both root CMake declarations; no generated binaries are enrolled.

### configuration-artifact-identity | high | Reconfiguration rewrote an existing Debug ZIP locator

The resumed Debug acceptance refused its existing ZIP because configuring Release
without the development executable had overwritten Debug's generated locator.
Resolved by moving locator publication from configure-time `file(GENERATE)` to a
CPack post-build script. It projects development-host presence from the assembled
manifest and binds the locator to archive and manifest SHA256 digests. Verification
rejects a replaced ZIP before deleting prior acceptance output and records the
tested hashes. The real-file replacement regression and two storage tests pass.
Final two-configuration acceptance is recorded in the following checkpoint.

### final-cmake-handoff | low | Current Windows interpreter packaging acceptance passes

Final integrated verdict: PASS for S01-S05 of the Windows interpreter foundation.
The resumed review covered the uncommitted CMake/platform split, isolated host,
assembly and acceptance helpers against the accepted foundation amendment, reusing
the prior corrected native-import, cleanup and pinned-build evidence. The two
resume findings above are resolved. No remaining critical or high findings were
identified within this scope.

Both final CPack archives passed full relocated acceptance. Debug includes
`python.exe` and `python_d.exe`; Release includes production only. Their hash-bound
results are `build/windows-x64/verification/Debug/result.json` and
`build/windows-x64/verification/Release/result.json`. Reconfiguring CMake preserved
both locators byte-for-byte. Release archive SHA256 is
`ce7bcb35a83c3cb25057bb47c7eaa1fc292aad18c2c9400257938dd884e2e3a7`;
its manifest SHA256 is
`ce36b6a5d59f8ab0df72c5be26a41fdc4f0a611f2a8e50222b887e6d1ad63b7d`.

The final outside-checkout installation at
`Y:/code/cadrumo-native-proof/CADRUMO final á 漢字` has that same manifest and
passes full cohesion and the package smoke test from an unrelated cwd. Current
Release CTest passes all four tests. The smoke checks cover 119 native identities
and 80 distributions. Three focused regression/storage tests, Ruff lint/format,
Windows-target ty and pinned Rust formatting pass. Ambient Cargo could not launch;
the pinned Rust formatter was invoked directly instead.

The earlier installed tree differs from the final artifact and its trace was not
reused. A fresh final-install trace passed with 71,288 scoped events, four writes
and zero lost events; every observed mutation was inside the supplied storage root.
Evidence is `Y:/code/cadrumo-native-proof/final-release-trace/summary.json` and its
scoped event file. The raw capture was removed. This proves the exercised parent
and child probe, not arbitrary-code containment or all product workflows.

The separate `native/application/` work and unrelated checkout changes are excluded.
Linux/macOS implementation, application-library integration, installers and public
release promotion remain outside this completed foundation. Product evidence binds
the assembled snapshot, not later unrelated edits in the shared checkout.

## Recommendations

Use the final hash-bound CMake artifact evidence for this handoff. Historical
artifact evidence remains scoped to its recorded source and layout. Preserve the
checked PDFium/pywin32 adaptations and rerun dependency smoke tests when their
inputs change. Linux formats/loaders and macOS compilation, signing and wheel
availability remain platform obligations.
