---
tags:
  - '#research'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:0c1278494e507b21a4fdf167f57f9c1ccd50d981d55c5a115b5cfe3a0c73231e'
related:
  - "[[2026-10-03-application-packaging-audit]]"
---
# `application-distribution` research: multiplatform identity and installation

The requested native distribution needs one identity projection and separate OS installation adapters. Existing Windows interpreter acceptance does not establish Linux/macOS native support or installer lifecycle behavior.

## Findings

### Shared metadata and platform implementation have different owners

`src/cadrumo/core/product_identity.py` owns product names; `pyproject.toml` owns version, author, license and project URLs. `CMakeLists.txt` currently repeats names, omits project version metadata and rejects non-Windows hosts. `dev/packaging/runtime_wheelhouse_contract.py` declares four targets and their deployment floors. Reusing these authorities avoids a second target or version inventory.

### Current CMake supports explicit project and target contracts

CMake 4.4 documentation supports project VERSION, DESCRIPTION, HOMEPAGE_URL and SPDX_LICENSE. Target compile properties, runtime selection and GNUInstallDirs express build and relocatable installation policy. No umbrella calendar-year compliance certificate exists in these interfaces. A project compatibility version must represent a real promise, not an invented API guarantee.

### Native installers provide lifecycle ownership

CPack supports WiX MSI, DEB, RPM and DragNDrop generators. Native package managers own registration and uninstall; a DMG transports an application bundle rather than providing an MSI-like repair database. Tauri also offers bundlers, making duplicate installer ownership an avoidable risk. CMake can package the assembled Tauri application and its private interpreter using one payload definition.

### Stable product and changing artifact identities are distinct

Windows AppUserModelIDs identify desktop applications; MSI UpgradeCode identifies an upgrade family while ProductCode and PackageCode follow installer versioning rules. Apple bundle identifiers and freedesktop desktop file names identify their desktop application. One shared reverse-domain application identifier can project those names, with scoped deterministic UUIDs only for fields that accept that lifetime.

### Evidence limitations

Windows pinned toolchains and Ubuntu x64 under WSL are locally available. No macOS or ARM64 runner has been established. Current source authority validation previously blocked a fresh product bundle. Synthetic packaging fixtures can validate installer mechanics, but cannot establish a release payload or native compatibility on unavailable targets. Semantic code discovery was temporarily unavailable; scoped source inspection located the existing owners.

## Sources

- `src/cadrumo/core/product_identity.py:20`, `pyproject.toml:1`, `NOTICE:1`
- `CMakeLists.txt:1`, `native/cmake/Packaging.cmake:1`, `dev/packaging/runtime_wheelhouse_contract.py:52`
- https://cmake.org/cmake/help/latest/command/project.html
- https://cmake.org/cmake/help/latest/module/GNUInstallDirs.html
- https://cmake.org/cmake/help/latest/cpack_gen/wix.html
- https://cmake.org/cmake/help/latest/cpack_gen/deb.html
- https://cmake.org/cmake/help/latest/cpack_gen/rpm.html
- https://cmake.org/cmake/help/latest/cpack_gen/dmg.html
- https://learn.microsoft.com/en-us/windows/win32/shell/appids
- https://learn.microsoft.com/en-us/windows/win32/msi/using-an-upgradecode
- https://learn.microsoft.com/en-us/windows/win32/msi/package-codes
- https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleidentifier
- https://specifications.freedesktop.org/desktop-entry/latest/
- https://v2.tauri.app/distribute/
