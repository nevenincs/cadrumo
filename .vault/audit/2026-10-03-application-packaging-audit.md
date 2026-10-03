---
tags:
  - '#audit'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:54c4cea69470b2456c471155ff63f5288d34a331b35e9b3fd7668b1a7ec7c20e'
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

## Recommendations

Finish the fresh CMake artifact acceptance before closing open plan steps. Historical
artifact evidence remains scoped to its recorded source and layout. Preserve the
checked PDFium/pywin32 adaptations and rerun dependency smoke tests when their
inputs change. Linux formats/loaders and macOS compilation, signing and wheel
availability remain platform obligations.
