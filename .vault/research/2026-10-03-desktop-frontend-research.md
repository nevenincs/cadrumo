---
tags:
  - '#research'
  - '#desktop-frontend'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:090f946bf8067dc4ea326d3a6e0bd825de14cb1ba99cc6a4a333e46a93100231'
related:
  - "[[2026-10-03-application-packaging-research]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
---
# `desktop-frontend` research: frontend stack and native integration boundaries

The requested frontend prototype can proceed independently of the package owners. Native execution and delivered-artifact acceptance need later integration evidence.

## Findings

### F1 - Existing owners support an isolated desktop source tree

`native/CONTRACT.md` reserves the desktop executable but no desktop source tree exists. `native/application/src/child.rs` exposes immutable executable/environment configuration and a standard-process command; it currently has no working-directory getter for a PTY adapter. `native/application/src/package.rs` owns Readiness and package inspection; Readiness currently lacks serialization. The desktop should request these extensions from that owner rather than recreate package verification or storage policy. `src/cadrumo/core/product_identity.py` owns display identity. `docs/` owns instructional content and Sphinx output. The core packaging plan explicitly leaves the Tauri frontend separately owned.

### F2 - React and Vite fit a bundled Tauri frontend

Tauri documents Vite integration and static frontendDist assets. React documents Vite as a build-from-scratch option. A server-rendered framework adds an unnecessary server deployment for this local shell. React state suffices for navigation, panels and prototype selection; query caches and global stores need actual data contracts before selection. Radix Tabs supplies keyboard and focus semantics without dictating appearance. CSS tokens keep presentation adaptable. This evidence favors React, TypeScript, Vite, Radix primitives and Lucide icons, with locked dependencies and browser-level checks.

### F3 - Terminal components still require native proof

xterm.js flow-control documentation requires coordination with the producer; bounded scrollback alone does not bound pending IPC/output. portable-pty exposes a native cross-platform PTY abstraction. Rendering an xterm viewport can prove frontend lifecycle and resizing, but cannot establish real Python, Textual, paste, mouse, exit or descendant cleanup. Keep renderer preview visibly disconnected until the owning library supplies verified child configuration. No mock echo shell counts as a native console.

### F4 - macOS path containment remains unresolved

Checked 2026-10-03: Tauri documents dataDirectory as unsupported on macOS; dataStoreIdentifier selects a WKWebsiteDataStore by identifier on macOS 14+. An identifier is not an API to select an absolute filesystem root. Neither that identifier nor incognito configuration proves all WebKit writes stay under the canonical user root. A macOS runner must trace WebKit processes, caches and restart/shutdown behavior. Compare a nonpersistent store and public native WebKit options; if neither satisfies policy, obtain a storage-owner decision before shipping. No private API or HOME redirection is justified by this investigation.

### F5 - Scope and discovery limits

The current user prioritizes prototyping documentation, graphical UI and an optional console/log pane while native dependencies are unfinished. Source ownership is native/desktop only. Code semantic search returned quiesce_admission_closed; targeted source inspection was used. Vault search succeeded. There is no agreed final executable-selection/environment DTO yet, and no platform execution evidence for this prototype.

## Sources

- `native/CONTRACT.md`
- `native/application/src/child.rs`
- `native/application/src/package.rs`
- `src/cadrumo/core/product_identity.py`
- `docs/index.md`
- https://v2.tauri.app/start/frontend/vite/
- https://react.dev/learn/build-a-react-app-from-scratch
- https://www.radix-ui.com/primitives/docs/components/tabs
- https://xtermjs.org/docs/guides/flowcontrol/
- https://docs.rs/portable-pty/latest/portable_pty/
- https://v2.tauri.app/reference/config/#datadirectory
- https://developer.apple.com/documentation/webkit/wkwebsitedatastore
