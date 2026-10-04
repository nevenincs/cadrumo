---
tags:
  - '#adr'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:d44d35421b0afee375c8efdd41267d4936ac2edd2a1e4adb3c2a9264b28c4c4b'
related:
  - "[[2026-10-03-application-packaging-research]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
---
# `application-packaging` adr: `authorized interpreter foundation` | (**status:** `accepted`)

## Problem Statement

The user authorized a compiled C interpreter, generated native contracts and a Windows packaging proof while requiring the broader application packaging ADR to remain proposed. An executable plan needs to distinguish that authorized foundation from unresolved application composition choices.

## Considerations

The existing research and proposed packaging ADR remain the design context. Settings, product identity, secure-storage taxonomy, exact Python builder version and locked Python dependencies already have canonical owners. Current implementation and build evidence are recorded in `native/CONTRACT.md` and `.artifacts/native/verification.json`.

## Considered options

- Ambient Python and duplicated C/Rust settings: rejected by the user's isolation and ownership requirements.
- Versioned C ABI with dynamic platform linkage: successfully compiled and exercised; adds an early application DLL dependency.
- Versioned C ABI with static platform linkage: selected after both linkage proofs. The executable's import table contains only Windows system libraries before main; shared policy still has one Rust source owner.

## Constraints

Acceptance is based on the user's explicit 2026-10-03 foundation brief and subsequent instruction to keep work to application layout and Python provisioning. It does not accept the unresolved choices in `2026-10-03-application-packaging-adr`. Tauri remains settled but unimplemented here. Linux has a mapping only; macOS implementation is deferred. No installer, provisioning service, runtime manager or storage migration is authorized. Existing local storage is ignored for this work as the user directed; core development defaults remain unchanged.

The native application consumes the existing Python product and its three exact-version distributions. Existing encryption, authentication, bucket/keystore separation and application authority remain unchanged. Native bootstrap supplies the packaged Settings environment before Python starts; it does not reimplement business configuration.

## Implementation

Authored sources are `native/interpreter/`, `native/platform/`, `native/package-layout.json`, `native/toolchain.json` and `dev/packaging/native/`. Generated bindings, SDK acquisition, builds and assembly stay under `.artifacts/native/`. The generator projects Settings names, identity and storage declarations; package-specific paths have one JSON owner. `native/CONTRACT.md` records the platform matrix.

Use the existing 3.13.11 release pin with the official CPython NuGet SDK, SHA256-pinned in the toolchain input. Compile the C host and bridge with matching headers and import library. This first build consumes upstream CPython binaries; it does not rebuild CPython from source. No CPython patch is required. The full 3.13 initialization API configures isolated import paths, disabled site/user-site and bytecode writes, explicit executable identity, UTF-8 streams and normal invocation parsing. The static host establishes restricted DLL lookup before loading the bundled Python DLL and initialization bridge.

The assembler maps qualified extension names to relocated native files under `bin/python`, rejects conflicting DLL basenames and unreviewed `.pth` files, and projects pywin32's required path entries without executing its `.pth` bootstrap. Two checked package adaptations address PDFium's explicit DLL location and pywin32's registry-derived extension/cache locations. pywin32 public COM aliases resolve to bundled extensions and its generated cache belongs under the declared user cache; before/after hashes are recorded. Authority is relocated once to `data/authority` and selected through the existing Settings field.

The packaged mutable root is Windows Known Folder LocalAppData plus `cadrumo`, with secure storage under `data` and temporary files under `tmp`. Inherited Settings/Python path overrides are cleared. The initial non-secret override allowlist is empty. This is controlled environment configuration, not an arbitrary-code security sandbox. Full process write tracing remains an acceptance obligation; Python audit events alone are insufficient.

## Rationale

The explicit user scope supports a bounded accepted foundation without promoting the whole proposed application ADR. Static platform linkage removes early application DLL search while the private bridge permits use of the public CPython initialization API after loader setup. Existing Python owners supply behavior and declarations; native code supplies installation-relative bootstrap.

## Consequences

A Windows interpreter and assembled base product now execute outside the checkout. DLL/static C consumers, real native imports, child startup, hostile Python environments, Unicode paths, missing dependencies and package immutability have measured evidence. The fresh documented build and scoped OS-level file trace now pass, and both initial high review findings are resolved. Trace evidence covers the exercised parent/child import and temporary/cache probe; later workflows require their own verification. Linux loaders, distribution format and native macOS implementation remain unproven obligations.

Later concurrent working-tree edits changed storage defaults and accepted overrides after the verified build. They have not been reconciled with this foundation contract. Reconciled by `2026-10-04-canonical-environment-adr`. Artifact evidence remains tied to the preserved native source snapshot; current-source approval and plan completion are open. The user must not infer approval of that changed policy from the prior binary proof.

## Amendment: CMake and platform ownership, 2026-10-03

The subsequent user instructions authorize CMake Debug/Release builds, install,
ZIP packaging, named cleanup targets, a bytecode standard-library ZIP, controlled
package paths, executable identity resources, full dependency smoke tests and
package-cohesion verification. They specify production `python` and a distinct
optional development executable with `_d` before the platform suffix. Both use
the release CPython ABI; a CPython debug-ABI distribution is not required. CADRUMO's
three wheels are built from source, while third-party wheels come from the locked
production dependency closure.

This amendment supersedes the earlier `.artifacts/native` build convention and
`bin/python` / unpacked-standard-library mapping. CMake defaults to
`build/windows-x64`, with configuration-specific `bin`, `stage`, `packages` and
verification outputs. The application contains `python.zip`, native dependencies
under `bin`, and production Python packages under `cadrumo/site-packages`.
`native/CONTRACT.md` owns the documented target and artifact naming reference.

The user explicitly requires platform-independent packaging orchestration.
`native/package-layout.json` owns shared package declarations;
`native/platforms/windows-x64.json` owns Windows physical names and SDK locations.
Shared helpers consume the selected merged contract. Platform-specific SDK,
loader, relocation, executable-resource and acceptance behavior belongs to explicit
platform backends. Only Windows has an implemented backend. Linux and macOS
mapping obligations remain open; no placeholder implementation implies support.

The user subsequently directed this work to consume the existing core storage
owner and preserve repository-local development defaults and explicit overrides.
This supersedes the earlier Known Folder and empty-override policy paragraphs.
Native generation projects `Settings.storage_env_var_names()` and storage taxonomy
values. The interpreter consumes the installed per-user default declared by the core
storage owner in `2026-10-04-canonical-environment-adr` and migrates no storage. Package-specific external binary directories are explicitly
allowlisted; they affect executable PATH without widening DLL search.

The old artifact and trace evidence remains historical. Verification of the CMake
and revised layout implementation must be recorded separately before the open
plan steps can be completed. The broader application packaging ADR remains proposed.

## 2026-10-04 installation scope amendment

The later accepted application-distribution ADR authorizes native installer definitions and installation lifecycle work across Windows, Linux and macOS. It extends this foundation's installer exclusion; it does not alter the interpreter, storage or loader contracts. Native runtime backend acceptance remains separately required.

## 2026-10-04 runtime manager extension

The accepted `2026-10-04-runtime-manager-architecture-adr` authorizes the per-user runtime manager (`cadrumo-manager`) on top of this foundation's platform crate. It extends this foundation's runtime-manager exclusion only. Roots and child environments still come from `native/platform`, and the interpreter, storage and loader contracts are unchanged.
