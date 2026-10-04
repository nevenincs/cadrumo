---
tags:
  - '#adr'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:e9522378c4ba3005b8759ff031a09be7fb7d5b172d018649b7e420fab60f19c6'
related:
  - "[[2026-10-03-application-packaging-research]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-adr]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
  - "[[2026-09-20-lud-authority-adr]]"
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
---
# `application-packaging` adr: `native application composition and data layout` | (**status:** `proposed`)

## Problem Statement

CADRUMO needs an application that installs and manages its existing Python CLI, TUI, MCP and runtime. Those interfaces do not yet provide the native desktop package, dependency provisioning or application lifecycle owner. This decision defines that boundary and its layouts; evidence is in `2026-10-03-application-packaging-research`.

## Considerations

Tauri is **settled by the user's instruction on 2026-10-03**, not a provisional candidate. The proposal status concerns the remaining composition and deployment choices. The older proposed `2026-07-25-standalone-executable-tier-adr` is not accepted coverage for this application. Existing runtime authority and canonical Python declarations must survive the addition of C and Rust.

## Considered options

- **Tauri application + controlled CPython + shared native foundation:** proposed; satisfies desktop, terminal and isolation requirements while retaining Python services.
- **Ambient Python and host-installed dependencies:** rejected; cannot ensure the package's own interpreter, libraries and paths.
- **Separate C/Rust/Python implementations of configuration and provisioning:** rejected; creates competing authorities.
- **Machine service, on-demand user supervisor, or detached runtime:** resolved by `2026-10-04-runtime-manager-architecture-adr`. A per-session manager starts at sign-in and owns the runtime's lifecycle. The on-demand supervisor hypothesis is retired, and unsupervised detachment remains rejected.

## Constraints

- `cadrumo.exe` is the Rust-backed Tauri desktop application. It presents a bundled open-source terminal and later GUI screens. The CLI/TUI remain independently usable console interfaces.
- `python.exe` is a controlled CPython build with a C initialization boundary. Bundled Python dependencies and native loaders must not fall back to host Python, virtual environments, current-directory imports or ambient DLL search.
- One per-user, per-channel root `U`, declared by the core storage owner and resolved per `2026-10-04-canonical-environment-adr`, contains all CADRUMO-controlled mutable data. The installed package is read-only during operation.
- Secure storage belongs under `U/data/`. Preserve existing encryption, bucket/keystore separation and runtime authentication. A directory name is not a replacement for secure storage.
- Chromium is downloaded, not included in the base package. macOS implementation is deferred to later worktrees; the architecture retains Windows/Linux/macOS targets.

## Implementation

We will assemble one native application around the existing Python release cohort, with the following proposed layout and shared components. There is no separate launchers directory or extra launcher product.

### Authorized interpreter foundation, 2026-10-03

The user explicitly authorized the controlled C interpreter foundation, generated contracts from existing Settings/storage owners, the Windows package mapping and an evidence-led C ABI linkage proof. This scope is executable while this record remains proposed for the unrelated unresolved composition and distribution choices. It does not accept the entire proposal.

Authored native projects live in `native/interpreter/` and `native/platform/`; package-only declarations in `native/package-layout.json`; contract generation and package assembly in `dev/packaging/native/`. Generated inputs, builds and staging live beneath `.artifacts/native/`. `native/CONTRACT.md` records the platform matrix and ownership map. Reuse the existing exact builder pin, `dev/packaging/release-python-version` (3.13.11), and the existing locked base dependency exporter.

The user subsequently narrowed this work to application packaging and Python provisioning: do not change core development storage defaults, inspect or migrate existing local storage, or block the foundation on that state. The proposed old-data rollout policy remains future work. Native bootstrap sets the packaged effective environment; existing Python services retain their semantics. No installed-runtime or UI management is introduced.

Static and DLL C consumers have both compiled and passed ABI version, error ownership and buffer release checks with Rust 1.96.0. Prefer static platform linkage in the bootstrap: the resulting executable imports only Windows system libraries before main. A private Python bridge loads after native loader setup and uses the full CPython 3.13 initialization API. Upstream CPython source is unmodified. This is a custom compiled host consuming a pinned CPython binary build, not a claim that CPython was rebuilt from source here.

### Installed package

```text
<CADRUMO>/
  cadrumo.exe                    Tauri application
  python.exe                     custom C interpreter host
  bin/
    aeat.exe                     existing public CLI name retained
    cadrumo-tui.exe               standalone console TUI
    cadrumo-mcp.exe
    cadrumo-runtime.exe
    python/                      libpython, .pyd modules, native dependencies
    platform/                    shared native DLLs, if dynamic linkage wins
  python/
    Lib/                         standard library
      site-packages/             exact-version CADRUMO and dependencies
  data/
    authority/                   immutable release authority
    components/                  pinned download/version manifests
    google/                      public OAuth client metadata, if selected
  docs/index.html                built offline user documentation
  README, LICENSE, NOTICE, warranty and third-party notices
```

The console executables share the interpreter bootstrap and invoke existing entrypoints. Renaming the public CLI is outside this decision. Use one `python/Lib` tree rather than competing `Libs/` and `lib/` roots. A generated loader map must preserve extension-module identities despite native files residing under `bin/python/`; the split is not validated until imports pass.

The release manifest binds interpreter ABI, Python packages, authority generation and downloadable component revisions. Ship one authoritative authority payload under `data/authority/`; adapt the canonical resource reader to that installed location without runtime regeneration or duplicate payloads. Retain referenced generations in user data before an upgrade removes them. Independent authority updates are undecided.

Tauri's embedded UI has its own `index.html` landing page. Build offline `docs/index.html` from canonical documentation sources; the app exposes it through its asset integration. No production development server. WebView2 is separate from downloaded automation Chromium. Candidate terminal components are `xterm.js` and `portable-pty`; selection requires a Windows interaction proof.

### User data

The layout under `U` is the existing taxonomy; no member moves (`2026-10-04-canonical-environment-adr`).

Compile defaults from canonical declarations; load only `U/config/application.env` plus explicitly allowed process overrides before Python startup. Generate the packaged example from that schema. Reserved interpreter, loader, custody and containment settings cannot be overridden. Python validates the same effective configuration; do not copy development `.env.example` defaults into releases.

Enforcement belongs in both native entrypoints and Python storage boundaries, with one policy implementation and generated contracts. Reject escaping paths and links; set child temp, cache, profile and model paths explicitly. Require write tracing across real packaged processes. OS-managed artifacts and the external Google browser need a documented boundary; environment isolation alone does not prove a filesystem sandbox. Existing `storage/` data requires an explicit refusal/instruction policy before rollout; no automatic migration or compatibility reader is authorized.

### Reusable foundations and ownership

| Component | Single responsibility |
| --- | --- |
| Contract generator | Project existing Settings/storage declarations into C/Rust bindings; UI DTOs expose public concepts, not internal nodes. Declare package-only metadata once; no duplicate inventories. |
| Native platform library (Rust) | Resolve roots, enforce containment, construct child environments and locate verified components. Expose a versioned C ABI to the interpreter host. |
| Interpreter bootstrap (C) | Initialize isolated CPython and its import/native-loader layout; consume platform contracts. No business or provisioning rules. |
| Application management library (Rust) | Download/verify/activate component versions and manage owned processes. Tauri and any future supervisor consume it. |
| Existing Python services | Remain owners of runtime authorization, storage semantics, Google flows and model admission/pull policy. Native management invokes typed interfaces. |
| Desktop/terminal integration | Tauri assets, open-source terminal and PTY bridge. Runtime-control UI belongs to the runtime manager (`2026-10-04-runtime-manager-architecture-adr`); the desktop may only start a missing manager by shell dispatch and request `reveal`. |
| Release assembler | Build the manifest, bindings, interpreter, console entrypoints, docs and installer from pinned inputs; verify the installed layout. |

C and Rust can reuse a DLL through a **versioned C ABI**. Use opaque handles, explicit lengths and allocator ownership; never expose Rust-native objects or unwind across the boundary. The early proof chooses `cdylib` versus `staticlib`; static copies built from one source do not create independent declarations. Process lifecycle is separate from library linkage.

### Provisioning and implementation order

Prefer core installation followed by explicit first-run capability downloads, deferred to first use if skipped. Chromium is pinned to Playwright. Local AI provisions a managed engine and selected models, reusing Python admission controls. Google authorizes on Connect. CLI/MCP must return actionable missing-component status without silently starting large downloads.

| Order | Exit evidence |
| --- | --- |
| 1. Windows development environment | Working, pinned MSVC/SDK, Rust MSVC, frontend and CPython builds; verify WebView2. Repair/select the currently unusable Rust executables first. |
| 2. Contracts and interop | Inventory canonical owners; generate bindings; C and Rust resolve identical layouts/errors; settle DLL/static ownership in a minimal executable proof. |
| 3. Interpreter and storage foundations | Real native dependencies import from the intended package; hostile host environment cannot redirect them; entrypoints agree on configuration; prove old-data refusal and trace writes. |
| 4. Tauri shell | Landing page, offline docs and real Textual TUI work through the bundled terminal; verify resize, input, shutdown and renderer data placement. |
| 5. Management and distribution | Resolve supervisor/service policy, then implement provisioning, recovery and runtime controls; verify fresh install, interrupted downloads, upgrade and uninstall. Apply shared foundations to Linux; defer macOS native work. |

Step 5's lifecycle questions are answered by `2026-10-04-runtime-manager-architecture-adr`: all-users and this-user installation scopes with side-by-side versions, a per-session supervisor process (`cadrumo-manager`) rather than a service, and runtime ownership independent of any window. No additional `cadrumo-host.exe` is introduced. Also open: WebView2 distribution, publisher-owned versus imported Google client registration, model/engine selection, Linux prerequisites and independent authority updates.

### Proposed reconciliation of accepted decisions

On adoption, apply these scoped amendments; this draft leaves accepted history unchanged:

- `2026-07-12-cadrumo-cli-executable-adr`: “`aeat` remains the sole command-graph CLI. `cadrumo.exe` is a separate graphical application; `cadrumo-tui.exe` hosts the standalone TUI. Neither is an alias for the CLI.”
- `2026-07-13-data-output-standardization-adr`: “Packaged application staging, including context-managed temporary files, stays under U. Its prior OS-temp exemption does not apply to this distribution; non-secret diagnostics and exports also remain contained.”
- `2026-09-02-cli-distribution-consolidation-adr`: “The pure-Python distribution commitment governs the CLI wheel. The separate desktop application may bundle that code with native interpreter and interface executables; it does not fork CLI semantics.”
- `2026-06-28-product-packaging-adr`: “The native application consumes the exact-version cohort. Its assembler may place the single public authority payload at package `data/authority/`, addressed through the canonical reader. Optional browser/model provisioning remains explicit and is coordinated by the application.”
- `2026-08-03-canonical-storage-management-adr`: “For the packaged application, the canonical taxonomy gains the approved application layout and generated native consumers. The layout under `U` is the existing taxonomy; no member moves. This replaces unrestricted absolute-path passthrough and third-party-cache escape treatment for that distribution.”
- `2026-09-20-lud-authority-adr`: “Packaged startup first enforces U containment; default creation and refusal of missing explicitly configured member paths remain unchanged. No external writable anchor is accepted.”
- `2026-10-03-runtime-without-service-manager-adr` retains runtime authority and the current absence of installed service management. This application decision covers its deferred owner; lifecycle installation remains unresolved here. Reuse `2026-09-26-mcp-purpose-authentication-adr` unchanged for runtime identity, custody and authenticated IPC.

## Rationale

The composition retains existing runtime and declaration ownership while adding the missing desktop and management layer. Generated contracts plus a narrow C ABI address cross-language drift; the two-root layout separates immutable release resources from user custody. Research findings F1–F6 establish the boundaries and the required proofs.

## Consequences

The application gains a coherent package and data contract, at the cost of native build/release tooling and explicit storage transition work. Tauri is settled. The listed lifecycle, distribution and ABI choices need evidence before implementation commits to them; this record neither installs services nor claims the package exists.
