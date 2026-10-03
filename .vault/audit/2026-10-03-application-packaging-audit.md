---
tags:
  - '#audit'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:b146a53e2cd82fae644948cbf8d7ad772f77060deac000210c640875e0304550'
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

## Recommendations

Artifact acceptance is established by acceptance-closure; concurrent-root-policy and concurrent-override-policy supersede current-source approval. Reconcile those interfaces before rebuilding and rerunning affected checks. Preserve the checked pywin32/PDFium adaptations and rerun their artifact tests when dependencies change. Linux distribution formats/loaders and macOS architecture, signing and wheel availability remain later platform obligations.
