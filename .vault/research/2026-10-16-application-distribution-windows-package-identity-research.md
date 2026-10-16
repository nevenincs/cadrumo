---
tags:
  - '#research'
  - '#application-distribution'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:975d597793341e291bf8bdaa50a70bbb1837ad7814545a5ca4a75f3d18733d3e'
related: []
---

# `application-distribution` research: `Windows package identity for one Task Manager entry`

The operator requires every Cadrumo process to appear under one "Cadrumo" entry in Windows Task Manager. Commit `286f2033e4` placed every desktop child in one kill-on-close Job Object and renamed the native images to Cadrumo, but Task Manager on build 10.0.26300 still listed each executable as its own top-level row. This record collects the evidence on what unifies different executables under one Task Manager entry and what that requires of the Windows distribution. Experiments ran on 2026-10-16 on the operator's machine (Windows 11 Pro 10.0.26300, developer mode enabled) with a throwaway `Cadrumo.SparseProbe` package, registered for the current user and removed afterwards.

## Findings

### Parent/child relationship and Job Objects do not group different images

Before any change, every Cadrumo process was a direct child of the Debug `cadrumo.exe`, yet Task Manager grouped only same-image chains (the python worker with its KDF python, the WebView2 tree). A Job Object changes lifetime, not presentation. An AppUserModelID does not help either: the reporter of WebView2Feedback #5628 tried one for exactly this split. The Windows 26H2 experimental app grouping (build 26340.9616) has no public API for applications to opt in.

### Package identity groups different images under the package display name

With the probe registered as a package with external location (a sparse package), a windowed `parent.exe` carrying the identity started `runtime.exe` (no identity), which started `agent.exe` (identity). The operator observed Task Manager showing `Cadrumo Probe (2)` containing the window and `agent.exe`; `runtime.exe` remained a separate row. Grouping follows package identity, not the parent chain, and the entry takes the package display name.

### Identity is not inherited; each image must claim it

A child image without the `msix` element in its embedded application manifest reported `APPMODEL_ERROR_NO_PACKAGE` (`GetCurrentPackageFullName` 15700) even as a direct child of an identified parent. Any image carrying `<msix xmlns="urn:schemas-microsoft-com:msix.v1" publisher=... packageName=... applicationId=.../>` matching the registered package received identity, whoever started it. A single `Application` entry sufficed: images other than its `Executable` obtained identity using the same `applicationId`. A manifested image nested below the external location (`versions/9.9.9/`) and one outside it entirely both received identity, so under developer-mode registration the location was not enforced. Microsoft's troubleshooting table states that identity is absent when the registered external location does not match the directory the application runs from, so a distributed registration must use an external location that contains every identified image; the canonical prefix containing `versions/<release>/` and the stable manager copy satisfies that, while a non-development location test remains outstanding.

### Identity is inert when the package is not registered

The same manifested image, run with no package registered, executed normally and reported no package. Embedding the element in every build therefore does not change development or pre-installation behaviour.

### No write redirection with unvirtualizedResources

With `rescap:unvirtualizedResources` declared and `uap10:RuntimeBehavior="win32App"`, `uap10:TrustLevel="mediumIL"`, an identified process writing to `%LOCALAPPDATA%`, `%APPDATA%` and `HKCU\Software` wrote to the real locations; nothing appeared under `%LOCALAPPDATA%\Packages\<family>`. Cadrumo's profile storage and settings would therefore stay where they are. Behaviour without that capability was not tested.

### Registration requires signing outside developer mode

`Add-AppxPackage -Path probe.msix -ExternalLocation <dir> -AllowUnsigned`, with the documented unsigned-namespace publisher (`OID.2.25.311729368913984317654407730594956997722=1`), failed unelevated with 0x80073D2B: an unsigned package cannot include Executable activations. Microsoft documents that an unsigned package with executable content must be installed for all users from an elevated session and is intended for testing, not distribution. Loose registration (`Add-AppxPackage -Register AppxManifest.xml -ExternalLocation <dir>`) succeeded only in developer mode and only with an ordinary publisher; the unsigned-namespace publisher was refused there with 0x80073D2D.

A distributed package is therefore a signed `.msix` whose `Publisher` equals the signing certificate subject. Microsoft documents two trust routes: a certificate from a trusted CA (it names Azure Trusted Signing) needs no trust step; a self-signed certificate needs its public certificate imported into `Cert:\CurrentUser\TrustedPeople` for a per-user registration, which needs no elevation, or `Cert:\LocalMachine\TrustedPeople` for a machine-wide one, which does. Per-user registration uses `AddPackageByUriAsync` with `ExternalLocationUri`; machine-wide registration stages with `StagePackageByUriAsync` and then calls `ProvisionPackageForAllUsersAsync`; removal mirrors each. A version already registered cannot be registered again, so each release needs a distinct package version. Microsoft recommends `ProcessorArchitecture="neutral"`. Developer machines can use loose registration without a certificate.

### Existing manifest ownership

One canonical process manifest, `native/interpreter/windows/host.manifest`, is embedded by the C hosts through `native/interpreter/windows/host.rc:3`, by the manager through `native/manager/build.rs:43`, and by the installer through `native/installer/build.rs:8`; CMake rejects linked images whose manifest diverges (`native/cmake/platforms/Windows.cmake:157`, `native/cmake/Manager.cmake:38`). The desktop image receives the default Tauri manifest through `tauri_build::build()` in `native/desktop/src-tauri/build.rs`. Version-resource strings come from the identity projection (`dev/packaging/native/identity.py`, `dev/packaging/native/platforms/windows.py:184`).

### Not investigated

Actual all-users provisioning on a disposable host; whether Microsoft's WebView2 processes join the host's group; interaction with native peer admission in the runtime (token claims added by identity); Task Manager behaviour on Windows 10. Each needs evidence on the real application or a disposable host.

### What the decision must settle

Package name, publisher and display name per channel; which installation role owns the registration; how every Cadrumo image carries the identity; the development registration path; and the certificate source for distributed builds.

## Sources

- https://github.com/MicrosoftEdge/WebView2Feedback/issues/5628
- https://learn.microsoft.com/windows/win32/shell/appids
- https://learn.microsoft.com/windows/apps/desktop/modernize/grant-identity-to-nonpackaged-apps
- https://learn.microsoft.com/windows/msix/package/unsigned-package
- https://windowsforum.com/news/windows-11-build-26340-9616-adds-task-manager-app-grouping-and-fixes-sandbox-update-error.448016/
- `native/interpreter/windows/host.manifest`
- `native/interpreter/windows/host.rc:3`
- `native/manager/build.rs:43`
- `native/installer/build.rs:8`
- `native/desktop/src-tauri/build.rs`
- `native/cmake/platforms/Windows.cmake:157`
- `dev/packaging/native/platforms/windows.py:184`
- commit `286f2033e4`

