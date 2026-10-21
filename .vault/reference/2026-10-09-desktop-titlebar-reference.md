---
tags:
  - '#reference'
  - '#desktop-titlebar'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:b51d4e9234934f7f57d0fe68c2a4f91273da1ea5c918b7e4c16bb6aa2f1ac231'
related: []
---

# Desktop title bar implementation evidence

## Summary

The approved visual study is native/desktop/frontend/src/dev/titlebar-proposal/TitlebarMockup.tsx and proposal.css. The user approved its lettering alignment, profile dropdown and dropdown-only sign out, then authorized production implementation and retirement of the duplicate Settings profile switcher on 2026-10-09.

Tauri documents decoration removal and native minimize, maximize, close and dragging at https://v2.tauri.app/learn/window-customization/. The pinned Rust API supplies Window::minimize, maximize, unmaximize, close, is_maximized, is_fullscreen and start_dragging. Window::close requests normal CloseRequested processing; destroy would bypass it.

native/desktop/src-tauri/src/app.rs composes every app command behind a per-launch token. native/desktop/src-tauri/tauri.conf.json.in grants no plugin JavaScript permissions. The documentation iframe must retain that refusal boundary. Window operations can reuse native Tauri Rust methods through token-checked app commands rather than granting core window capabilities.

native/desktop/frontend/src/shell/signIn.ts owns account state and coherent profile listing, selection, creation, sign-in and sign-out. components/SignIn.tsx currently exports Account for Settings and contains the credential dialog. Settings.tsx owns frontend preferences. Account must be retired, with account feedback moved to one header dropdown and the existing credential dialog retained.

native/desktop/src-tauri/src/app.rs already refuses macOS; this change must not claim macOS application support. Native window state persistence is independently owned by shell/window_state.rs. Native resizing and window placement remain Tauri responsibilities.

## Verification

Verify header interactions against the real App and scenario host, token refusal through the Rust dispatcher, native API routing and close lifecycle. Browser scenarios prove presentation only. A native Windows build and packaged window check are required for native control evidence; unavailable Linux or macOS execution must be reported separately.
