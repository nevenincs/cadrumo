# Desktop frontend prototype

The Textual TUI occupies the main workspace. React owns the surrounding shell,
welcome page, offline documentation reader, and optional Python console/log pane.
The terminal viewports are real xterm.js instances with input disabled until the
native session integration exists. There is no emulated Python prompt or backend.

The stack is Tauri 2, React, strict TypeScript, Vite, Radix Tabs, Lucide, CSS tokens,
and xterm.js with its fit addon. React state is transient. No browser persistence,
runtime manager, downloader, shell plugin, filesystem plugin, or invoke command is
enabled. Lockfiles own dependency resolution.

## Build and inspect

Run from the repository root with the existing development Python environment,
Node/npm, CMake and the project's native Rust toolchain available:

```powershell
cmake -S native/desktop -B build/desktop-prototype
cmake --build build/desktop-prototype --target desktop-frontend-install
cmake --build build/desktop-prototype --target desktop-frontend-build
cmake --build build/desktop-prototype --target desktop-frontend-check
cmake --build build/desktop-prototype --target desktop-frontend-test
```

Playwright requires its test Chromium installation (`npx playwright install chromium`
from `frontend/`). This test browser is neither Tauri's WebView nor the product's
downloadable automation Chromium.

For native builds, put the canonical Rust toolchain's `bin` directory on PATH or
set `CADRUMO_DESKTOP_RUST_BIN` to it, then run:

```powershell
cmake --build build/desktop-prototype --target desktop-host-build
$env:CADRUMO_DESKTOP_PREVIEW_DATA_DIR = (Resolve-Path build/desktop-prototype).Path + '/desktop/webview'
& ./build/desktop-prototype/cargo/desktop/debug/cadrumo.exe
```

After building, `cmake --build build/desktop-prototype --target desktop-preview`
launches the same executable with that preview directory. The Windows-only
`desktop-host-test` target checks the native WebView with a temporary local
debugging port and closes its owned application afterward. It requires an
interactive desktop session; Session 0 returned WebView2 error 0x80070578
(invalid window handle) in the initial execution environment.

The last command is the Windows development preview. Its explicit WebView path
is a developer-selected test location, not a delivered Settings default. macOS
native startup refuses until storage containment is resolved. Linux execution
has not been established. This standalone CMake entry is independent of the shared
package build; enrollment in that build belongs to the foundation handoff.

For browser preview, set `CADRUMO_CMAKE_BINARY_DIR` to the absolute selected build
directory and run `npm run preview` in `frontend/` (port 1421). `npm run dev` uses
1420. `CADRUMO_DEV_PYTHON` optionally selects the existing development interpreter
for build-time product identity projection.

## Source and output owners

- `frontend/`: authored React shell, build configuration, lockfile and browser tests.
- `src-tauri/`: authored host, configuration, Rust source and lockfile.
- `scripts/host.mjs`: snapshot the authored host into the build tree, generate icons
  from the canonical SVG and build static assets into the executable.
- Selected binary directory: `desktop/frontend`, `desktop/vite-cache`,
  `desktop/host`, `desktop/icons`, `desktop/test-results*`, and `cargo/desktop`.
- `frontend/node_modules` contains installed development dependencies and is ignored.

Product names come from `src/cadrumo/core/product_identity.py`; the mark comes from
`docs/_static/cadrumo-favicon.svg`. Five existing explanatory chapters are projected
from `docs/explanation/`. The preview converts only inline MyST roles and anchors;
it refuses fenced Sphinx directives rather than lose generated command examples.
References outside this subset show an explicit full-manual notice. The final
desktop must consume the canonical Sphinx output, including command projections
and search, through its bundled docs integration.

## Native consumer handoff

The current application owner defines `native/application/src/package.rs::Readiness`
and `child.rs::ChildConfiguration`. There is no agreed serialized frontend contract
yet. Integrate with those owners rather than inventing a second readiness enum or
resolving executables/environment in TypeScript.

The PTY adapter needs an immutable verified interpreter selection, working
directory, complete child environment, terminal mode and canonical user-data
locations. The current child type exposes executable/environment and a standard
process Command; agree the missing PTY-facing working-directory access with its
owner. Build-time DTO generation should originate from the owning Rust contracts.
Package inspection must remain side-effect free. TUI and Python session ownership
is distinct from the explicitly started runtime's lifetime.

Prove portable-pty with the packaged interpreter before selecting final bridge
details: input, resize, Unicode boundaries, paste, mouse, bounded queues and output
acknowledgements, child exit, window closure and descendant cleanup. Scrollback
limits alone do not establish transport backpressure. Preserve typed runtime
unavailability; do not add automatic runtime start/repair or OS registration.

## Open packaged acceptance

| Target | Evidence still required |
| --- | --- |
| Windows x64 | Packaged PTY/Textual/Python interaction, read-only relocated install, hostile Python environment, child cleanup and WebView/child write tracing |
| Linux x64 | Native toolchain/build, WebView prerequisites and all packaged acceptance |
| Linux ARM64 | Native toolchain/build, WebView prerequisites and all packaged acceptance |
| macOS ARM64 | Public WebView storage containment solution, native build/signing and all packaged acceptance |

Canonical target identities and floors remain owned by
`dev/packaging/runtime_wheelhouse_contract.py`. This table is an acceptance worklist,
not another build target registry.

Tauri's macOS `dataDirectory` override is unsupported. `dataStoreIdentifier` selects
a WebKit store by identifier; it does not select the required absolute filesystem
root. A nonpersistent store also needs OS write tracing. Resolve this through the
storage owner and public WebKit APIs before enabling native macOS startup. See
[Tauri configuration](https://v2.tauri.app/reference/config/#datadirectory).
