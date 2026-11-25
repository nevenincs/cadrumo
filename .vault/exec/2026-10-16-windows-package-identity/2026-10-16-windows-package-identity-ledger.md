---
tags:
  - '#exec'
  - '#windows-package-identity'
date: '2026-10-16'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:df21864b148f2f0db743f0f0b06df491e0fd17260245e8a8a834b2a8748989c2'
related:
  - "[[2026-10-16-windows-package-identity-plan]]"
---

# `windows-package-identity` ledger

## Changes

- `S01` `M` `dev/packaging/native/identity.py`
- `S01` `M` `dev/packaging/tests/test_distribution_identity.py`
- `S01` `verify:` `pytest dev/packaging/tests/test_distribution_identity.py` -> `pass`
- `S02` `M` `dev/packaging/native/platforms/windows.py`
- `S02` `M` `dev/packaging/native/platforms/linux.py`
- `S02` `M` `dev/packaging/native/platforms/macos.py`
- `S02` `M` `dev/packaging/native/metadata.py`
- `S02` `M` `dev/packaging/native/platforms/tests/test_windows.py`
- `S02` `M` `native/interpreter/windows/host.rc`
- `S02` `M` `native/cmake/platforms/Windows.cmake`
- `S02` `M` `native/cmake/Manager.cmake`
- `S02` `M` `native/manager/build.rs`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S02` `verify:` `cmake --build --preset debug --target app-payload embedded-manifest check` -> `pass`
- `S02` `verify:` `Release app-payload embedded-manifest check` -> `pass`
- `S03` `A` `native/desktop/src-tauri/windows/desktop.manifest`
- `S03` `M` `native/desktop/src-tauri/build.rs`
- `S03` `M` `native/desktop/scripts/tauri.mjs`
- `S03` `M` `native/desktop/tests/packaged/host.mjs`
- `S03` `M` `.gitignore`
- `S03` `verify:` `Debug and Release desktop builds` -> `pass`
- `S04` `A` `dev/packaging/native/package_identity.py`
- `S04` `A` `dev/packaging/native/tests/test_package_identity.py`
- `S04` `verify:` `pytest dev/packaging/native/tests/test_package_identity.py` -> `pass`
- `S05` `M` `dev/packaging/native/package_identity.py`
- `S05` `verify:` `package_identity register --build build/windows-x64` -> `pass`
- `S05` `verify:` `GetPackageFullName on cadrumo.exe, cadrumo-runtime.exe and msedgewebview2.exe children` -> `pass`
- `S05` `verify:` `locator-check: -` -> `pass`
- `S05` `by:` `plan-closure`
- `S06` `verify:` `locator-check: -` -> `pass`
- `S06` `by:` `plan-closure`
- `S07` `verify:` `locator-check: -` -> `pass`
- `S07` `by:` `plan-closure`
- `S08` `verify:` `locator-check: -` -> `pass`
- `S08` `by:` `plan-closure`

## Notes

- `S02` RC truncates macro names at 31 characters and the Visual Studio generator ignores `COMPILE_LANGUAGE:RC;` the define is a host.rc source property.
- `S03` Tauri embeds the manifest with layout whitespace collapsed; registration compares parsed XML.
- `S05` Task Manager grouping and signed-in agent processes await operator observation.
- `S05` Superseded: package-identity ADR `superseded_by` the single-binary ADR; removal is single-binary S07
- `S06` Superseded: package-identity ADR `superseded_by` the single-binary ADR; removal is single-binary S07
- `S07` Superseded: package-identity ADR `superseded_by` the single-binary ADR; removal is single-binary S07
- `S08` Superseded: package-identity ADR `superseded_by` the single-binary ADR; removal is single-binary S07
