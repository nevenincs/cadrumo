---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-08'
body_schema: 'body-v2'
body_hash: 'sha256:e87612c4a2912de0aa003e17297b55bab1265d9e4ba5b3abd3f518f36a28a896'
related:
  - '[[2026-10-04-application-distribution-research]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-09-02-cli-distribution-consolidation-adr]]'
  - '[[2026-07-13-product-rename-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
---
# `application-distribution` adr: canonical identity and native installation | (**status:** `accepted`)

## Problem Statement

The user requested implementation of modern CMake package definitions, identity, compatibility, compiler policy, installation and uninstall, explicitly for Windows, Linux and macOS. Existing interpreter-only coverage does not settle this installation lifecycle.

## Considerations

Evidence is in `2026-10-04-application-distribution-research` and the prior interpreter audit. The existing product, project metadata, target inventory and Settings owners must remain authoritative. Tauri remains the desktop application; an absent shell is not replaced by a misleading interpreter shortcut.

## Considered options

- One CMake/CPack distribution graph with native OS adapters: selected to fulfill the explicit CMake requirement and reuse the verified payload.
- Independent Tauri and CPack installer metadata: rejected because it creates competing identities and upgrade ownership.
- Windows-only conventions copied to Unix: rejected by the explicit multiplatform instruction.

## Constraints

Authorization is the user's 2026-10-04 instruction to implement identity, build policy and installation lifecycle, with explicit Windows/Linux/macOS scope. This accepts these scoped implementation choices, not the unrelated application composition proposal. Source publisher, license, names and URLs come from existing owners. The stable application ID is `md.neve.cadrumo`; channel suffixes distinguish coexistence identities, independently of Debug/Release configuration. Stable identities never derive from build paths, timestamps or machine identity.

Reuse the canonical four-target inventory and declared deployment floors. CMake policy compatibility is explicit and target flags are scoped. A declared OS floor requires eventual execution evidence; generated metadata is not that evidence. Do not claim native compatibility for missing runners or placeholders.

Installation manages immutable program files. User data stays under the existing Settings/storage owner and is preserved on uninstall. No service, scheduled task or storage migration is introduced. Login start for the runtime manager is registered in the installation scope. Signing is explicit and must not claim publisher verification without actual credentials and verification.

## Implementation

Generate shared identity into CMake and native metadata from Python owners. Populate project version, description, homepage and license. Include source, target, channel and interpreter identities in build evidence. Project platform-native desktop metadata and installer configuration. Package MSI on Windows, DEB/RPM and archives on Linux, and an application bundle/DMG on macOS. Offer all-users and this-user installation scopes for MSI/DEB/RPM, Applications-folder bundle installation on macOS, and explicit prefix installation for development/archives. Install versions side by side under a version-independent entry point per `2026-10-04-runtime-manager-architecture-adr`. Native package managers own uninstall. Prefix uninstall is manifest-bound and preserves unowned or modified files and user data.

The existing application-core plan retains Rust application internals and native backend/provisioning commitments. This plan owns identity, common CMake policy and installer definitions; shared changes preserve its integrated tests. Native build gaps remain explicit prerequisites for final per-target application acceptance.

### Linux desktop runtime prerequisites, 2026-10-08

The Linux Tauri desktop uses distribution-managed GTK 3 and WebKitGTK 4.1 runtime packages. CMake/CPack remains the sole owner of CADRUMO's package identity, payload, registration, and upgrade lifecycle. Tauri's independent installer generator is not introduced. The package's CPython, Python extensions, and locked Python dependencies retain their existing private loading and relocation contracts.

The canonical glibc 2.28 floor remains an ABI ceiling for every ELF file CADRUMO distributes. It is not, by itself, a sufficient desktop host requirement. Desktop execution also requires the declared GTK, GLib, WebKitGTK, and related native APIs, their distribution-managed runtime dependencies, and an admitted graphical session. A distribution whose repositories cannot satisfy those prerequisites is not supported for the desktop merely because its glibc meets the floor. Distribution dependency packages may impose a newer host glibc minimum; package metadata and compatibility documentation must expose that resulting requirement without changing the artifact's own ABI floor or claiming unsupported older hosts.

A single typed Linux desktop-runtime contract declares the enrolled desktop application image, its permitted external SONAMEs, API minimums, and DEB/RPM provider requirements. Shared native generation projects that contract into payload verification, native package metadata, and an inventory-bound prerequisite manifest distributed with both native packages and archives. The envelope applies only to the explicitly enrolled desktop image. It does not widen the interpreter, manager, extension-module, or arbitrary package-image dependency policy. New direct native dependencies require an explicit contract change and matching validation.

Linux assembly continues to reject wrong architecture, a GLIBC requirement above the canonical floor, unknown dependencies, dependency names containing paths, conflicting package basenames, and bundled files shadowing declared system dependencies. For the desktop image only, declared external dependencies are resolved through the native host runtime. Packaged images carry no build-prefix RPATH/RUNPATH, and runtime launch does not inject build SDK directories through LD_LIBRARY_PATH or other loader overrides. Private build SDKs are compilation inputs whose identities and selected providers are recorded; they are not silently copied into the application or accepted as installed-runtime evidence.

DEB and RPM metadata require the declared runtime providers and minimum versions. Native shlibdeps/automatic requirement tools supplement the explicit policy; they do not replace it or infer a new policy from whichever libraries happen to be installed on a build host. Package inspection verifies the actual dependency metadata, architecture, identity, payload inventory, and existing installation refusal gates. Provider aliases or distro-specific package names must be explicit and verified against native package metadata. A requirement cannot be weakened merely to make an artifact build or install.

Auxiliary Linux archives carry the same desktop prerequisite manifest and retain the same externally managed desktop runtime boundary. Archive relocation and this-user prefix installation do not mean dependency-free operation, confer privilege, or install system libraries. Missing runtime prerequisites are reported before managed installation or launch where the owning entry path can inspect them; direct ELF invocation may also fail at the native loader. The existing runtime-only package configuration keeps its existing dependency policy when the desktop image is absent.

The native distribution owns WebKit helper processes, injected bundles, media and image-loader plugins, accessibility components, TLS/certificate integration, fonts, themes, and the matching graphics/driver stack through its runtime packages. CADRUMO neither substitutes an arbitrary host-discovered library closure nor bundles parts of that stack while assuming the rest are interchangeable. Application payload integrity remains bound to CADRUMO-owned files; system prerequisite/provider evidence is recorded separately, so an OS security update does not invalidate the application file inventory.

The initial locked Rust dependency graph requires GTK 3.24, GLib/GObject/GIO 2.70, and WebKitGTK API 4.1 with WebKit version 2.40 or newer. The exact subordinate requirements and enabled features belong to the typed contract and verified lockfile evidence. These are declaration/build requirements, not a claim of proven minimum-runtime compatibility. Validation must cover the actual distributed binary's required symbols against admitted provider libraries, native package dependency resolution, absence of private SDK paths, and real launch/rendering/IPC behavior on clean supported native runners. Build-host probes and compilation alone do not discharge those obligations. Existing installation and lifecycle acceptance gates remain closed until their independent protections and runner evidence pass.

This refinement settles the previously open Linux desktop-prerequisite boundary. It does not change the accepted interpreter foundation, application identity, manager authority, installation scope, storage policy, signing requirements, or native lifecycle ownership. Fully bundled GTK/WebKit delivery would require a separate decision covering complete resources, helper relocation, GPU/system boundaries, licenses, security updates, and graphical acceptance.

Authorization: the user's continuing instruction to code and build everything except signing certificates, with dependency installation authorized, covers this native package dependency refinement. It is accepted as a refinement of the existing distribution decision; it does not authorize installation or lifecycle tests on the two non-disposable hosts. Grounding: the measured Linux dependency-closure failure and provider investigation recorded in 2026-10-04-application-distribution-audit, the locked Cargo feature evidence under build/windows-installers-x64/verification/manylinux-gtk324, and Tauri's native Debian/RPM dependency documentation (https://v2.tauri.app/distribute/debian/ and https://v2.tauri.app/distribute/rpm/). Cross-reference preview was bounded (33 judged candidates, 23 clipped); direct inspection of the distribution, interpreter foundation, proposed composition and desktop-shell decisions found no accepted obligation to bundle the Linux desktop browser stack.

## Rationale

One shared identity projection keeps product names, installer IDs and platform registration consistent while OS adapters retain native lifecycle behavior. Content hashes identify exact artifacts; stable namespace-derived IDs identify upgrade families. These have different lifetimes.

## Consequences

This extends the earlier interpreter foundation's installer exclusion for this authorized work. PyPI release delivery remains unchanged; native application packaging is an additional authorized deliverable, refining the earlier CLI distribution deferral without replacing its Python release pipeline. Public publication and signing credentials remain separate external actions. Final acceptance requires real payload build/install/uninstall evidence on every declared target, including the runtime manager's registration and lifecycle on disposable hosts.
