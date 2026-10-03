---
tags:
  - '#research'
  - '#application-packaging'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:1d84d5d091a039fbcb786ee1bd040bbd6cd11193453078dc9dfb07527f4bca43'
related:
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-adr]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

# `application-packaging` research: `native application layout and foundations`

How should the new desktop application assemble CADRUMO without duplicating its runtime authority or configuration? The evidence supports a native application layer around the existing Python product. Tauri is a user-settled input; the remaining research concerns isolation, shared C/Rust foundations, provisioning and deployment. Findings reflect the working tree and official documentation inspected on 2026-10-03; initial findings preceded native compilation; F7 records the subsequent Windows interpreter proof.

## Findings

### F1 — Packaging fills an explicitly deferred responsibility

`2026-10-03-runtime-without-service-manager-adr` defers installation, supervision and dependency provisioning to future application bundling. Existing runtime authentication, custody and worker containment remain authoritative. `2026-06-28-product-packaging-adr` owns the exact-version Python/knowledge release cohort; `2026-09-02-cli-distribution-consolidation-adr` owns Python CLI distribution. A native desktop package needs a scoped extension, not another implementation of those services. Current public scripts include `aeat`, `mcp` and `cadrumo-runtime` (`pyproject.toml:136`).

### F2 — Tauri supports the landing page; automation Chromium is separate

Tauri embeds `frontendDist` assets and serves `index.html`; its production UI needs no development server. Windows uses WebView2, Linux WebKitGTK and macOS WKWebView. Downloading Playwright Chromium does not supply Tauri's renderer. Windows installer options include per-user installation and alternative WebView2 distribution modes; neither an administrator service nor a fixed WebView2 bundle follows automatically from choosing Tauri. Sources S1–S3.

Open-source `xterm.js` plus `portable-pty` is a credible terminal composition, retaining the Python Textual TUI as a separate process. It is a candidate, not a tested integration: keyboard handling, resize, Unicode and ConPTY need a Windows proof. Sources S4–S5.

### F3 — Isolation needs native loading controls and an explicit packaged environment

CPython's isolated `PyConfig` can disable ambient Python configuration and set explicit import paths before initialization. A `._pth` file can constrain path initialization; ordinary `.pth` processing is different and can execute import statements. Neither mechanism alone isolates native DLL lookup or confines filesystem writes. A custom C host must establish DLL loading, paths and child environments before importing CADRUMO. Sources S6–S7.

The code already has canonical storage declarations (`src/cadrumo/core/storage_taxonomy_locations.py:88`), but its default secure-state anchor ends in `storage/` (`src/cadrumo/core/config_state_root.py:214`). The subsequent user brief supplies `cadrumo/data/` for the delivered package and excludes development-default changes and existing-storage migration from this foundation. Native bootstrap supplies the existing Settings field; it does not change Python storage semantics. Existing Settings explicitly exclude dotenv discovery (`src/cadrumo/core/config.py:183`); packaged overrides therefore need deliberate loading, not an assumption that `.env.example` is executable configuration. That example includes development settings (`env/.env.example:252`).

The evidence favours a build-generated native projection of the existing declarations. Independently maintained C, Rust, Python and UI path tables would recreate the drift the storage ADR removed. Proposed containment must include WebView profiles, browser scratch, model-engine state, temporary files and child-process defaults. OS-managed artifacts and the external OAuth browser require an explicit boundary; environment configuration is not an OS sandbox.

### F4 — C and Rust can share a library through a C ABI

Rust supports `cdylib` for foreign-language dynamic linking and `staticlib` for static linking. Its native Rust ABI is not stable. A versioned C ABI with fixed-width values, explicit buffer lengths, opaque handles and provider-owned release functions allows the C interpreter and Rust application to consume one implementation. Allocating in one DLL and freeing through another CRT can fail. Sources S8–S10.

A shared DLL reduces duplicate binary code but introduces early loader and version coupling. Static linkage from the same source preserves canonical logic while simplifying bootstrap loading. Neither option shares process state: lifecycle ownership still requires a process and IPC. The early proof should choose linkage, allocator ownership and ABI compatibility before platform logic spreads across modules.

### F5 — Provisioning has three different owners

Playwright requires browser revisions matched to its release and supports `PLAYWRIGHT_BROWSERS_PATH` (S11). Chromium can therefore be an application-managed download; Linux system dependencies remain a packaging concern.

Google needs an OAuth application registration, packaged client libraries and per-user authorization, not a local Google service. Desktop client metadata cannot be treated as a confidential embedded secret; Google requires an external user agent. Current CADRUMO imports an operator's desktop client configuration (`src/cadrumo/adapters/outbound/google/records.py:105`). A publisher-owned registration, consent/verification and transition from that flow remain undecided. Sources S12–S13.

Ollama offers standalone Windows binaries, but redirects models, logs, temporary files and other state separately. `OLLAMA_MODELS` alone cannot prove containment (S14–S15). Existing `pull_runtime_model` requires operator intent and admission checks and expressly does not spawn the daemon (`src/cadrumo/application/provisioning_runtime.py:863`). The application should own binary/process provisioning and reuse that Python model policy. Install-time downloads simplify first launch but enlarge installation; opt-in first-run/first-use downloads preserve a usable core and avoid unsolicited large transfers. Timing remains a proposal.

### F6 — Windows toolchain readiness is the first implementation gate

Read-only probes on 2026-10-03 found Visual Studio C++ installations through `vswhere.exe`, but `cl.exe` was absent from the current PATH. `rustc --version` and `cargo --version`, resolved under `X:/ci-shared/cargo/bin`, failed with “No application is associated with the specified file”. Node reported `v26.10.0`; CMake was discoverable. No working native compilation or WebView2 prerequisite was verified.

The first step is selecting and activating compatible Windows SDK/MSVC, a working Rust MSVC toolchain, a pinned frontend toolchain and the chosen CPython build. The Python package currently requires Python >=3.13 (`pyproject.toml:6`); its native dependencies need compatibility proof before fixing an interpreter version. Official prerequisites/build instructions: S16–S17. Linux packaging follows the common foundations; native macOS work is deferred. Installer upgrades, signing and full write tracing were not investigated.

### F7 — Windows compilation and relocation are now measured

`native/toolchain.json` pins the official CPython 3.13.11 NuGet SDK by SHA256, MSVC 14.44.35207, Windows SDK 10.0.26100.0 and Rust 1.96.0 for x86_64-pc-windows-msvc. The exact interpreter version comes from `dev/packaging/release-python-version`. The build invokes installed tools explicitly, avoiding the broken ambient Rust shim. C static and DLL consumers and the Rust consumer passed. The host import table contains Windows system libraries only; CPython is loaded after restricted loader setup. This compiles the custom host against upstream binaries, not CPython source, and requires no CPython patch.

The locked Windows base closure supplies 77 third-party distributions. `dev/packaging/native/product.py` composes existing snapshot, authority and wheel owners for the three exact-version product distributions. The assembled CADRUMO 0.5.1 product runs outside the checkout. `dev/packaging/native/verify.py` proves Unicode/spaces, unrelated cwd, pure/native imports, child identity, hostile Python settings, ignored executable .pth, missing or invalid bundled libraries, hostile/missing qpdf and unchanged package hashes. The fresh documented three-wheel build and assembly also passed; current evidence is `.artifacts/native/verification.json` for `.artifacts/native/repeatable/package`.

Relocation exposed PDFium's explicit ctypes path and pywin32's registry-derived extension/cache paths. `dev/packaging/native/assemble.py` applies two checked package adaptations, records before/after hashes, and maps public win32com extension identities. The corrected artifact imports `win32com.shell.shell` and selects the declared COM cache. These are package patches, not upstream CPython changes.

Python audit writes pass within the declared root. Initial Process Monitor captures were incomplete; an initial WPR capture dropped events and is not acceptance evidence. A subsequent nonpaged WPR profile and scoped parser completed without event loss: the repeatable trace command observed 2013 parent/child events and four writes, all file mutations under the declared root. Its source is dev/packaging/native/platforms/windows_trace.ps1; evidence is C:/Users/hello/cadrumo-native-proof/repeatable-trace/summary.json. This covers the exercised import/tempfile/COM-cache probe, not all product workflows. The existing all-platform wheelhouse also lacks the pinned pikepdf macOS wheel; that is a later platform obligation, not evidence of Windows incompatibility.

## Sources

Repository locators are given at each finding; cited ADRs preserve the existing decision coverage.

- S1: https://v2.tauri.app/reference/config/
- S2: https://v2.tauri.app/concept/process-model/
- S3: https://v2.tauri.app/distribute/windows-installer/
- S4: https://xtermjs.org/
- S5: https://docs.rs/portable-pty/latest/portable_pty/
- S6: https://docs.python.org/3.13/c-api/init_config.html
- S7: https://docs.python.org/3.13/library/sys_path_init.html
- S8: https://doc.rust-lang.org/stable/reference/linkage.html
- S9: https://doc.rust-lang.org/reference/items/external-blocks.html
- S10: https://learn.microsoft.com/en-us/cpp/c-runtime-library/potential-errors-passing-crt-objects-across-dll-boundaries?view=msvc-170
- S11: https://playwright.dev/python/docs/browsers
- S12: https://developers.google.com/identity/protocols/oauth2/native-app
- S13: https://developers.google.com/identity/protocols/oauth2/policies
- S14: https://docs.ollama.com/windows
- S15: https://docs.ollama.com/faq
- S16: https://v2.tauri.app/start/prerequisites/
- S17: https://devguide.python.org/getting-started/setup-building/
