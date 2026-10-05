---
tags:
  - '#audit'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:d009d8d81afe0fd896f82d90604e9ebdbc96fa8b1e7882dfb598cf87b98be0d3'
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

## Recommendations

Complete real payload/native lifecycle checks on every supported target and resolve the WiX tooling/license prerequisites before declaring application-distribution complete. Preserve the existing storage owner and keep native package-manager uninstall separate from the development-prefix removal helper. Use the native distribution recipe documented in native/CONTRACT.md; do not relabel synthetic package checks as product launch evidence.
