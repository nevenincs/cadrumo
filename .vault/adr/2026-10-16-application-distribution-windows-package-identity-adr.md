---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:a28be3cb5d34c5613143c4ea26599ca6f1d74fa0cbeb6e05b888618f856bf4fa'
related:
  - "[[2026-10-16-application-distribution-windows-package-identity-research]]"
  - "[[2026-10-07-application-distribution-windows-versioned-msi-adr]]"
  - "[[2026-10-16-native-build-incremental-adr]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `application-distribution` adr: `Windows package identity: one registered Cadrumo application` | (**status:** `accepted`)

## Problem Statement

The operator requires every Cadrumo process on Windows to appear as one registered "Cadrumo" application. Task Manager lists the desktop, runtime, manager, agent service, agent and bundled Python as separate top-level rows even when they are direct children of the desktop window and share its kill-on-close Job Object. Windows unifies different executables only through package identity; Cadrumo is an MSI-installed, unpackaged application today and has none.

## Considerations

2026-10-16-application-distribution-windows-package-identity-research records the evidence: probe observations on build 10.0.26300 that package identity groups different images under the package display name, that identity is claimed per image through the embedded `msix` manifest element and is not inherited, that it is inert when no package is registered, that `unvirtualizedResources` leaves AppData and HKCU writes in place, and Microsoft's registration and signing requirements. 2026-10-07-application-distribution-windows-versioned-msi-adr, as amended by 2026-10-16-native-build-incremental-adr, owns installation roles: immutable version files and an independently maintained shared registration in one scope-aware MSI. 2026-07-12-cadrumo-cli-executable-adr's 2026-10-16 amendment fixes the OS-visible name as `Cadrumo`. 2026-10-04-runtime-manager-architecture-adr owns runtime admission, which rests on native image and kernel peer evidence.

## Considered options

- Keep separate rows with consistent names and one lifetime boundary (the state after commit `286f2033e4`): rejected by the operator as not meeting the requirement.
- Full MSIX packaging of the application: replaces the accepted MSI delivery, side-by-side version retention and native transaction ownership; rejected.
- AppUserModelID, Job Objects or process ancestry: do not change Task Manager grouping per the research; rejected.
- A package with external location (sparse package) registered by the existing installer, with every Cadrumo image claiming its identity: selected.

## Constraints

Accepted 2026-10-16: offered this option with a recommendation, the operator replied that it is critical that the application is registered. The certificate source for distributed builds was not chosen in that reply and is recorded below as an open prerequisite.

1. One package identity per channel, projected by the distribution identity owner (`dev/packaging/native/identity.py`) and never restated by consumers: package name, publisher, application id `Cadrumo`, display name equal to the native application name (`Cadrumo`, `Cadrumo Preview`), `ProcessorArchitecture="neutral"`, and a package version equal to the release version with a zero fourth component. Windows refuses to register a version that is already registered, so re-registering the same release removes the earlier registration first. Development builds use a distinct development publisher, so a development identity can never equal a distributed one.
2. Every Cadrumo-owned executable image the application runs carries the `msix` element for its channel's identity: the desktop, the stable and versioned manager, the entrypoint hosts, the bundled interpreter and the bundled agent image. `native/interpreter/windows/host.manifest` remains the single authored process manifest; the build renders from it an identity-bearing variant for application images, while the installer and native maintenance runner, which are not application processes, keep the plain document and carry no identity. The desktop's manifest keeps Tauri's required content and adds the same element. Divergence checks compare each linked image with the rendered document for its role.
3. The manifest declares `uap10:AllowExternalContent`, `runFullTrust` and `unvirtualizedResources`, `uap10:TrustLevel="mediumIL"`, `uap10:RuntimeBehavior="win32App"` and `AppListEntry="none"`. File-system and registry locations, storage roots and profile custody are unchanged; any observed redirection is a defect, not a new storage location.
4. Registration is a SharedRegistration resource with that role's lifetime, scope isolation and anchors. Its external location is the canonical installation prefix, which contains `versions/<release>/` and the stable manager copy. Per-user installation registers with `AddPackageByUriAsync` and `ExternalLocationUri`; per-machine installation stages with `StagePackageByUriAsync` and provisions with `ProvisionPackageForAllUsersAsync`. Registration removal follows registration-role removal. Version products never register or remove the package.
5. Package identity is presentation and platform-integration identity only. It grants no runtime, manager, service or profile authority; admission continues to rely on the native image, module, invocation and kernel peer evidence its owners define, and must not start trusting package claims. An unregistered package, a failed registration or a missing identity leaves every process fully functional.
6. A failed or refused package registration does not roll back an otherwise committed installation; the maintenance result reports it as incomplete registration work. Registration never runs before the installation commit and never from the manager, runtime or desktop.
7. Distributed registration uses only a signed `.msix` whose `Publisher` equals the signing certificate subject. No unsigned-namespace publisher, elevated all-users unsigned install or developer-mode loose registration is used by an installer. Until the certificate source is chosen and its signing step exists, the installer authors no registration and the images still carry the inert element.
8. Development builds may be registered only through an explicit developer command that loosely registers a built stage tree in developer mode with the development publisher, and removes that registration on request. CI, tests and builds never register a package.

## Implementation

Extend the identity projection with the package fields; render the canonical process manifest and the package manifest from it; feed the rendered manifest to the C hosts, manager and desktop image; add the developer registration command; then add per-user and per-machine registration and removal to the native maintenance owner within the shared-registration feature after the single-MSI port of 2026-10-16-native-build-incremental-adr lands, and sign the package once the certificate source is chosen. The certificate source is an open operator decision: a certificate chaining to a public root, which needs no trust step in either scope, or a Cadrumo self-signed certificate whose public half the installer imports into the scope's TrustedPeople store, which the per-machine scope can do only elevated. Acceptance requires the real application to show one Cadrumo entry containing every Cadrumo process, unchanged storage locations and runtime admission, and both installation scopes registered and removed on a disposable host.

## Rationale

A package with external location is the only documented mechanism that unifies different executables in Task Manager while keeping the accepted MSI delivery, side-by-side versions and transaction ownership. Claiming identity per image is required because identity is not inherited, and it is safe because the claim is inert without registration. Placing registration in the shared-registration role gives it the version-independent lifetime it needs and keeps immutable version products untouched.

## Consequences

Every Windows image's manifest becomes channel- and build-kind-specific, so manifest divergence checks and reproducibility inputs include the identity projection. Releases need a signing step and a certificate before distributed registration works; development machines can use the developer command meanwhile. Microsoft's WebView2 processes are not Cadrumo images and may remain outside the group; that is observed in acceptance, not assumed. Package identity also enables Windows features such as notifications and startup tasks; adopting any of them is a separate decision. This record extends the shared-registration resources listed in 2026-10-07-application-distribution-windows-versioned-msi-adr constraint 3 and changes no other installation obligation.
