---
tags:
  - '#audit'
  - '#cmake-e2e-build'
date: '2026-10-08'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:9a07a5bbcb11676d4dfca52bca110687d5c568146671e162b144834ed360e20a'
related:
  - "[[2026-10-08-cmake-e2e-build-plan]]"
---
# `cmake-e2e-build` audit: CMake release and executable verification

## Scope

Review S01's CMake transcript maintenance targets, generated documentation expectations, verification settlement wait, and release execution evidence in the Windows x64 preset. Preserve unrelated concurrent checkout changes.

## Findings

### executable-evidence | low | Required release and launch evidence remains pending

PENDING at 15:08 Madrid on 2026-10-08. The latest `verify-release` invocation failed after 5445 seconds in the strict documentation gate. Modelo 390 annual verification stopped waiting while its operation remained running, and supply-binding seed filing lost its runtime connection. Other page comparisons reported no divergence. The isolated annual sequence subsequently passed through `user_docs_sequences_check`; this does not replace the required page-level gate. The full Modelo 390 page check is currently owned by the main build session. No completed executable launch is claimed.

### maintenance-boundary | low | Explicit refresh preserves the ordinary release gate

`native/cmake/Docs.cmake` adds separate check and refresh targets using the managed CMake Python and published authority dependency. Page and sequence selectors are mutually exclusive; duplicate pages are removed before target creation. Neither target changes `user_docs_build`, weakens strict compilation, nor refreshes expectations during an ordinary release build. `native/CONTRACT.md` documents the maintenance controls.

### verification-wait | low | Verification separates operation settlement from bounded transport

`src/cadrumo/entrypoints/cli/runtime_modelo_verification.py` retains the 60-second transport budget and passes a distinct 1800-second settlement budget using the existing registered-operation protocol, following calculation's established behavior. It does not retry submissions, report an unknown mutation as successful, or change projection validation. Annual verification evaluates a stored quarterly chain and workflow gates. Ruff lint, format, and whitespace checks pass; the focused live page and full release checks remain required.

### refreshed-oracles | low | Registry changes account for the reviewed expectations

Refreshes were performed through CMake's explicit owning sequence target. The reviewed M303 revision changes follow the published first-quarter 2026 registry selection. Seven added M390 declarations raise the inspection contract from 19 to 26 formulas; the refreshed annual output includes their computed base and deduction fields. Annual tax assertions remain 1470.00 accrued, 105.00 deductible, and 1365.00 payable. No expected exit status or verification completeness assertion was weakened. The shared checkout contains concurrent edits, so final staging must retain ownership boundaries.

### cache-isolation | low | Local compilation preserves validation without acquiring the shared cache

The later package-build request authorizes continued assembly and launch testing. CADRUMO_DOCS_SHARED_CACHE defaults ON; OFF routes the same producer into the existing canonical build directory without copying from, writing to, or locking the shared site. The branch still checks input stability before returning; build_roots retains authority checks, local output inventory validation and completion publication. Thirteen CMake-driven driver tests pass, including unchanged shared-cache contents, unavailable shared locking, and changed-input refusal. The ordinary strict compile and sequence gate are unchanged. Live package/launch evidence remains pending.

### executable-build-order | low | Compilation no longer waits for documentation packaging

The desktop compiler consumes generated frontend assets and the native contract, not the packaged documentation tree. Removing user_docs from desktop-host-build produced the actual Release cadrumo.exe successfully in 1m 26s. Bundle still depends on user_docs, and desktop-headless-test depends on bundle. Its full-source package root is derived from the configured stage path. The subsequent CMake launch attempt in Session 0 started the executable but refused package_unavailable because assembly had not yet produced the manifest and interpreter. Successful CLI startup remains a required check.

### stable-source | low | Package verification uses the existing product source snapshot

Five enrolled Python sources changed during the live checkout's 18:19 compile. Stopped only the owned CMake tree before it spent more time on a result the input-stability guard would reject. Configured and built the existing CMake-owned `product/build/source` snapshot using its standard preset; no validation was removed and no source snapshot was copied manually. Configuration and four exact-version product wheels passed; the strict documentation gate and package launch remain pending in session 64610. The parent product target must remain idle while that snapshot supplies the build.

The required `build/windows-x64/_deps/builder/Scripts/python.exe -m dev.quality.types` run exited 1 with 54 Windows diagnostics, all in the concurrently edited `src/cadrumo/core/darwin_transport.py` (12 ty, 12 pyrefly, 30 basedpyright); Linux and Darwin scans reported zero. This is an external verification limitation, not a passing aggregate or a reason to alter unrelated transport work.

### distribution-stages | low | User-directed separation of compilation and verification

The user's latest instruction explicitly requires the complete uncompressed distribution as one core CMake producer, with ZIP and release verification separate. `app-distro` now owns assembly; `bundle` is its compatibility alias, ZIP is no longer an ALL target, and `release` delegates to `verify-release`. The latter requires an unfiltered `user_docs_verify` target. Packaging renders committed transcripts with strict Sphinx warnings; ordinary documentation compilation retains its previous sequence-check default. No runtime launch policy or Session 0 detection was changed. Generated Visual Studio references confirm default builds omit ZIP/release, ZIP consumes the distribution, and release requires live sequence verification.

### search-staging | low | Search stamping must preserve the rendered page's line endings

The first separated build rendered all four languages successfully, then failed its stored-documentation round-trip check for all 1316 HTML pages. The first differing byte in en/404.html was a line terminator: the indexed page had 818 LF line endings, while reconstruction had 818 CRLF endings; normalizing the terminators made the bytes identical. Both Pagefind stamping paths explicitly rewrote pages with LF, conflicting with native-platform reconstruction. Read and write now preserve existing line endings. Real Pagefind integration tests cover LF and CRLF pages in both indexed and excluded paths. All 44 CMake documentation-driver and Pagefind tests pass. No byte-identity assertion was removed. The corrected full distribution build remains pending at this checkpoint.

## Recommendations

### final-distribution-review | low | Complete directory and direct packaged launch accepted

PASS for the user's requested uncompressed distribution. Reviewed the final CMake producer/consumer graph, strict rendering selection, newline preservation and CLI parser regression coverage as one workflow. The corrected `app-distro` build exited 0; documentation staging retained byte-for-byte reconstruction checks and the package manifest declares bundled documentation. All six package CTest tests passed (8.15 seconds) with `CADRUMO_DESKTOP_PACKAGE_ROOT` unset. From `Y:/`, CMake invoked the packaged EXE with version, help and no arguments; every invocation exited 0 and version reported CADRUMO 0.5.1. The complete artifact is `Y:/code/cadrumo-worktrees/tui/build/windows-x64/product/build/source/build/windows-x64/stage/Release/app`, including `cadrumo.exe`, manager, interpreter, native entrypoints, dependencies, authority, manifests and documentation. No standalone executable or runtime-only directory is used as handover evidence.

Verification: 44 documentation-driver and real Pagefind tests pass, including LF/CRLF preservation and explicit/default sequence-check selection. Repository lint and type checks pass. Import loadability passed for 4542 modules, the subordinate checker passed, and the missing-PATH graph component passed when rerun through its owner with the absolute CMake-managed executable (15 contracts). Repository-wide formatting still reports an unrelated calendar.py line; all changed files pass formatting. ZIP/full live release verification were not run under the latest explicit scope. GUI interaction cannot be verified in Session 0; production selection code was not changed. Earlier failed-build entries are historical and remain intact.

Latest scope follows the user's explicit requirement for an on-disk distribution. ZIP creation and full live release verification remain separate, subsequent operations.

### Latest executable evidence

Headless acceptance passed against the CMake runtime-only bundle at `build/windows-x64/product/build/source/build/windows-x64/stage/Release/app`. All five `ctest --preset release -R '^bundle\.' --output-on-failure` tests passed (8.93 seconds). The standard standalone desktop preset built `build/windows-x64/product/build/source/build/desktop-windows-x64/cargo/desktop/release/cadrumo.exe` using the full-source preset's pinned Rust root. `desktop-headless-test` passed exact CLI stdout/stderr/exit parity, Unicode arguments, hostile Python environment, launch guards and logs. `desktop-run` then displayed the real application start/help output and exited 0. Native logs confirm successful CLI exits for version, help and no arguments.

The user explicitly prohibited coding a special Session 0 condition. Inspected `native/desktop/src-tauri/src/launch.rs` and `native/platform/src/desktop.rs`: the existing selection checks interactive desktop availability (visible window station and OpenInputDesktop), not a session-number comparison. No production launch logic or headless test was modified by this task. `CADRUMO_TEST_HEADLESS_SESSION=1` only enables the existing test assertions.

Full desktop release acceptance remains PENDING: strict documentation compilation failed after 4940 seconds on a bank-import runtime deadline and a test-runtime shutdown refusal. Runtime-only mode intentionally omits bundled documentation and the desktop image. The independently built desktop host ran against this verified runtime package; this does not establish a complete GUI distribution or installer. S01 remains open. Code changes have since been incorporated into the shared checkout's HEAD by another workstream; these task records preserve the remaining acceptance gap.

Finish the page-level check, diagnose any remaining runtime failure, then rerun `verify-release` and `desktop-headless-test` through CMake. Append the resulting evidence before closing S01. Do not mark a compiled prerequisite as executable acceptance.
