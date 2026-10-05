---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:63de29eccd9d4d6c9835c3eb4f3a8f6463446a915e392f8828b203b9ca72b349'
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

## Rationale

One shared identity projection keeps product names, installer IDs and platform registration consistent while OS adapters retain native lifecycle behavior. Content hashes identify exact artifacts; stable namespace-derived IDs identify upgrade families. These have different lifetimes.

## Consequences

This extends the earlier interpreter foundation's installer exclusion for this authorized work. PyPI release delivery remains unchanged; native application packaging is an additional authorized deliverable, refining the earlier CLI distribution deferral without replacing its Python release pipeline. Public publication and signing credentials remain separate external actions. Final acceptance requires real payload build/install/uninstall evidence on every declared target, including the runtime manager's registration and lifecycle on disposable hosts.
