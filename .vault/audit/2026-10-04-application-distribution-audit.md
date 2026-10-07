---
tags:
  - '#audit'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:5ae30b3a69c18449a189e1029355dc27ad563d16791daa2d331c05da56b1b18b'
related:
  - "[[2026-10-04-application-distribution-plan]]"
---
# Application distribution verification

## Scope

Review of application-distribution S01-S03 and the available S04 evidence. Baseline is the parent of e36f2e139c; scope includes the two identity/CMake commits and the current installation changes. Independent registry, localization and desktop functionality edits are excluded. The two desktop build-file edits under review only consume generated identity; existing terminal and frontend implementation is preserved.

## Findings

### identity-and-build | low | Canonical identities and current Windows build checks pass

The shared product owner supplies md.neve.cadrumo. Project metadata supplies publisher, contact, license and version. UUIDv5 upgrade families remain stable across version changes and separate target/channel identities; the Windows stable GUID is pinned by a regression assertion. Desktop configuration now projects name, identifier and version from the same generated identity. Debug/Release is independent of installation channel. CMake project metadata, target-scoped C17/hardening and configured minimum versions are explicit. Fresh Release interpreter/product assembly completed with 119 relocated native modules; all six CTests passed. The Linux GCC 15.2 fixture configured, built and ran with the compiler/linker policy, including PIE probing. This is not glibc-floor proof.

### installation-contract | low | Synthetic cross-platform metadata and guarded prefix lifecycle checks pass

The focused Python suites passed 34 tests on Windows. They cover all four target layouts, stable upgrade IDs, channel isolation, literal CMake projection, macOS bundle metadata, Windows shortcut AppUserModelID/HKLM registration, payload tampering, wrong-target refusal, redirected paths, receipt preflight and modified/unowned file preservation. Linux WSL generated a DEB from an explicitly synthetic payload, verified its metadata, installed it into an isolated prefix, and removed it using the receipt. The macOS CMake distribution project configured on Windows; this verifies generation only. Windows CPack emitted WiX sources with the custom shortcut component linked into its feature. Ruff, formatting and ty checks apply to the touched Python helpers and tests; Node syntax and standalone desktop CMake configuration passed.

### native-release-acceptance | medium | Full cross-platform release acceptance remains pending

The real Windows runtime ZIP was generated from the newly assembled payload, installed into an isolated prefix, and passed the bundled smoke test. Its prefix uninstall removed owned files while retaining a deliberately modified NOTICE file and an unowned user file. All 11,651 ZIP file hashes matched the installation receipt. The archive SHA256 is 092df1112ad10d12208051fdc0b31ca10a878c96b624333e77dd45b53392c6b6; evidence is build/distribution-runtime-windows/archive-verification.json. Windows MSI creation is unverified: WiX 7 tooling is present, its UI extension is missing, and extension setup reports WIX7015 requiring operator acceptance of the OSMF EULA. No terms were accepted and no MSI was installed. RPM tooling is unavailable in the Linux environment. Linux native runtime backends, Linux ARM64 and macOS ARM64 native runners, macOS desktop containment, GUI launch/upgrade/uninstall cycles and signing/notarization remain prerequisites. Existing application-core work owns the native runtime backends; installer metadata does not establish their compatibility. S04 must stay open. Overall verdict: PENDING, with no critical or high code finding in the reviewed scope.

### vault-tooling | low | Feature checks report six non-code warnings

The feature-scoped vault check passed structure, schema, links, execution mapping and body checks. It reported retained ledger template annotations, a missing generated feature index, and four CLI-written modified stamps that use the prior UTC date rather than the record's local date. The installed correction and index commands expose no dry-run option, so the repository's mandatory preview rule prevents applying those optional repairs through these verbs. No record metadata was hand-edited.

### windows-upgrade-ownership | high | Current combined MSI policy removes prior versions

2026-10-07 follow-up requested complete installer/upgrade acceptance. Current native/cmake/distribution/CMakeLists.txt uses CPACK_WIX_INSTALL_SCOPE=perMachine, one release product, the shared family UpgradeCode and CPack's default template. The pinned CMake 4.4.3 template, C:/Program Files/CMake/share/cmake-4.4/Modules/Internal/CPack/WIX.template.in, declares MajorUpgrade Schedule=afterInstallInitialize with AllowSameVersionUpgrades=yes. Microsoft's Major Upgrades documentation confirms the Upgrade table/RemoveExistingProducts mechanism removes related products; it is not side-by-side ownership. dev/packaging/native/installation.py now stages manager packages under versions/<version> but includes the shared entry, marker, registration and complete version in that same MSI ownership. A versioned directory name does not preserve the previous product. Only machine scope is authored. REVISION REQUIRED against the accepted manager Versions and Prerequisites constraints; distribution S03 must reopen before native MSI acceptance. This is current configuration/template evidence, not a claim that an MSI was built or installed in this run.

### windows-acceptance-prerequisites | medium | Live upgrade acceptance depends on unimplemented manager integration and a disposable interactive host

Manager IPC/readiness handoff, scoped login registration, cutover/rollback, failed-version catalogue policy and native obsolete-version/uninstall detection remain open in runtime-manager-architecture P02.S12, P03.S14 and P04.S16-S17; required preference/opt-out behavior remains P02.S13. native/manager/src/main.rs currently supports start, internal breakaway and --version; it forwards at startup before its session lock, then runs the selected supervisor. That does not cut over an already-running owner. Do not turn a catalogue fixture or passing source startup test into a cross-version readiness result. This Windows 11 build 26200 agent runs in Session 0; Docker reports linux, Hyper-V lists no VM, and Containers-DisposableClientVM is disabled. Requested a disposable Windows VM/runner and access method. No real registry write, MSI install, login registration, reboot or logout was performed on this development host.

### windows-installer-baseline | low | Focused current staging and identity checks pass

uv run --no-sync pytest -q -n 0 over test_native_installation.py, test_native_installation_windows.py, native/tests/test_distribution_prepare.py and test_distribution_identity.py passed forty selected tests, with two explicit POSIX-only skips. The default lane deselected all eight Windows-only cases; a separate explicit windows_only run is required and recorded when it completes. This suite exercises the real CMake/CPack ZIP graph and isolated filesystem receipts over synthetic payloads; it does not build a release MSI or prove live product upgrade. Evidence: var/storage/development/.logs/test-runs/2026-10-07/20261007T140211.327983Z-pytest-55172-ab65f9d7/run.log.

### windows-installer-primary-sources | low | Installer ownership proposal uses native component and upgrade rules

Primary sources consulted on 2026-10-07: https://learn.microsoft.com/en-us/windows/win32/msi/major-upgrades ; https://learn.microsoft.com/en-us/windows/win32/msi/changing-the-component-code ; https://cmake.org/cmake/help/latest/cpack_gen/wix.html . The Microsoft component rules distinguish changed component identities and target locations from compatible shared resources. CPack documents one install scope and a custom WiX template, plus matching WiX UI-extension/tool prerequisites. These facts support separate immutable version products and a shared registration owner; they do not certify the proposed implementation or waive release licensing/signing and native acceptance gates.

### windows-handle-acceptance | low | All eight Windows-only prefix-removal safety checks pass

The separately selected command uv run --no-sync pytest -q -n 0 -m windows_only dev/packaging/tests/test_native_installation_windows.py passed all eight cases with no skip/deselection. The real Windows tests prove retained-handle deletion, intervening byte and file-identity preservation, parent junction refusal, sharing violation refusal, and retaining the file/parent against replacement during hashing. Combined current baseline: forty-eight passed, two POSIX-only skips. Evidence: var/storage/development/.logs/test-runs/2026-10-07/20261007T140454.339924Z-pytest-66216-04ca4fc7/run.log. Native MSI lifecycle remains unexecuted.

### windows-decision-placement | low | Proposed MSI ownership refines existing topology without claiming acceptance

2026-10-07-application-distribution-windows-versioned-msi-adr records the proposed format-specific ownership choice, with immutable version products behind one shared registration product per scope/channel/target. Existing accepted distribution and manager commitments remain unchanged; no supersession or acceptance was inferred. The whole ADR catalogue listing was followed through its next_offset after the first five hundred records: all 551 records were returned across two pages. Relevant named installation/packaging/manager records were inspected. One configured hosted cross-reference pass judged the draft against thirty-two candidates from a bounded pool of 192 among 551 corpus records, with thirty-eight requests and 122673 input tokens. It returned already-declared refines/dependency links to the accepted distribution and manager ADRs; source and twenty-one candidate inputs were clipped, so the complete named parent records were also read locally. No hosted score grants authority or establishes complete corpus conflict coverage. Dependent implementation and full release acceptance remain pending.

## Recommendations

Complete real payload/native lifecycle checks on every supported target and resolve the WiX tooling/license prerequisites before declaring application-distribution complete. Preserve the existing storage owner and keep native package-manager uninstall separate from the development-prefix removal helper. Use the native distribution recipe documented in native/CONTRACT.md; do not relabel synthetic package checks as product launch evidence.
