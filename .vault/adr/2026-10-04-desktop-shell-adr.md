---
tags:
  - '#adr'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:eb9279095614c4ac069f340d2f8163227dc14bbac3750362e93f0dead2e0beb4'
related:
  - "[[2026-10-04-desktop-shell-reference]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
---

# `desktop-shell` adr: `Desktop shell` | (**status:** `proposed`)

## Problem Statement

The user's 2026-10-04 frontend spec replaces the fullscreen terminal in `cadrumo.exe` with three elements:

- The bundled user documentation is the main element. The window opens on its index, and the docs must be readable, browsable and searchable.
- A right-side flyout shows the aggregated Python backend logs.
- A bottom panel has two terminal tabs: the bundled Python interpreter with the Cadrumo environment set, and the Cadrumo TUI.

This needs a decision now because it fixes several things at once:

- how documentation is packaged and served under a strict webview CSP
- the IPC and cross-origin message protocols between the shell, the documentation and the Rust host
- the keymap shared with the TUI
- how far the shell may reach into backend state

Evidence is in `2026-10-04-desktop-shell-reference`.

## Considerations

- The window CSP admits only `'self'`, so documentation, search, fonts and scripts must all be local (`2026-10-04-desktop-shell-reference`).
- The documentation set is about 435 MB in about 63,000 files across four languages. Every file can't be compiled into the binary.
- The documentation runs third-party JavaScript (jQuery, Furo, mermaid, Pagefind). Tauri IPC must stay out of its reach.
- The TUI and REPL own F1 to F10, Ctrl+P, Ctrl+Q, Ctrl+C, Ctrl+K, Escape and plain keys. WebView2 accelerators collide with several of these.
- The shell grants no authority and adds no CLI semantics. Runtime launch, supervision, availability and authentication belong to the runtime and to a runtime manager. The user has said the runtime needs that manager (MCP clients can't connect otherwise), so runtime management is a required dependency of the desktop application. Its design is still a draft, its decision record is still to be written, and it waits on the user's ruling. `2026-10-03-runtime-without-service-manager-adr` is interim, so this record ties its constraint to ownership, not to that record.
- Admitted work is owned by the runtime and survives the client disconnecting (`2026-09-26-mcp-purpose-authentication-adr`). Interaction bearers are local to one process. An operation waiting on review or confirmation from a TUI that has exited settles under the runtime's rules, by refusal or expiry, and a restarted TUI can't answer it.
- When no storage root is set in the environment, installed code resolves it against the process's current working directory (`src/cadrumo/core/storage_environment.py:10`, `:19`; `src/cadrumo/core/config_state_root.py:92`). Two child processes started in different directories can therefore resolve different storage roots, and so different runtime endpoints. The delivered per-user default is still an open obligation of the storage owner (`native/CONTRACT.md`).
- The user removed earlier unapproved landing content. Anything outside the spec and the four additions approved on 2026-10-04 needs the user's approval.
- Localized chrome uses the informal singular. It comes from the canonical locale catalogues, with no parallel translation table.

## Considered options

- **React shell with a cross-origin documentation iframe:** chosen. Terminal sessions and the flyout survive documentation navigation, overlays compose normally, and origin separation keeps documentation scripts away from IPC.
- **Documentation as the top-level page, with terminals and logs in native child webviews:** rejected. It depends on Tauri's unstable multi-webview feature, nothing can overlay the documentation, and keyboard focus between webviews is fragile.
- **Documentation embedded in `frontendDist`:** rejected. It means 63,000 files compiled into the binary, and a Rust rebuild for every documentation edit.
- **Documentation served from the development docs server (port 8788):** rejected. It isn't a packaged artifact, and dev and package would behave differently.

## Constraints

- The documentation origin gets no IPC, plugin or capability. Tauri 2.12.1 treats every registered custom scheme as a local origin, so it resolves the documentation frame to the same capabilities as the shell. The refusal therefore belongs to the application, through a per-launch shell token:
  - the host mints the token at startup from at least 32 CSPRNG bytes, and never logs or persists it
  - it is injected by an initialization script into the top frame only, never into all frames
  - the shell reads it once from a namespaced, non-enumerable global and keeps it in module scope
  - every app command takes the token as an argument, or in the `x-cadrumo-token` header for raw-body `terminal_write`, compares it in constant time, and refuses a mismatch with `invalid_arguments`
  - the shell never posts the token to the iframe and never puts it in a URL or in storage; the bridge envelope never carries it
  - defence in depth: the documentation CSP `connect-src 'self'` blocks the IPC fetch transport, and no plugin JavaScript command is granted to the webview
- Nothing remote loads in the webview. External https and mailto links open in the system browser through a host command that revalidates the URL. Every other scheme is refused.
- The shell never captures F1 to F10, Ctrl+P, Ctrl+Q, Ctrl+C, Ctrl+K, Escape or plain keys while a terminal has focus.
- The log view keeps "available", "missing" and "unreadable" sources distinct from an empty list. It only reads the log and never truncates, rotates or deletes it.
- The log reader expects rotation to be late, skipped or racing, because several processes share one `RotatingFileHandler` file and a rename on Windows fails while another process has the file open. It never infers that a process exited from a file event. It also doesn't assume that profile workers log to this file.
- `source` on a log record is an open enumeration. A later runtime-manager source must not break the shell.
- Terminal output is never dropped. Backpressure pauses the PTY reader instead.
- The shell holds no runtime connection and no runtime authority. It never opens the runtime endpoint, and it shows no runtime availability, authentication request, timeout or control. Until the runtime-management ruling, the TUI tab shows only the TUI's own output, and desktop-shell plan S12 stays blocked.
- The shell shows no authentication UI. Login stays in the TUI, the runtime's profile worker launches the Cl@ve browser, and approval prompts belong to the runtime manager or the TUI.
- The shell never caches, forwards or persists session, lease, receipt or credential material between TUI processes. Restarting a session starts a new process that goes through admission again.
- No shell or host copy says that work completes after a terminal closes or the window closes.
- The host adds no storage-root, log-directory or other Settings variable to its child processes except the storage root that the Settings-owned projection itself resolved. The projection emits that root as the Settings storage-root variable, so the host, both terminal kinds and the CLI passthrough resolve the same root whatever their working directory. A regression test in a relocated packaged layout proves it (desktop-shell plan S02). The root that is pinned still depends on the launch directory until the storage owner settles a delivered per-user default. That question is open with the user.
- This record proposes replacing these items in `2026-10-03-application-packaging-adr`: the separate Tauri `index.html` landing page, `docs/index.html` exposed through asset integration, and the runtime-control UI listed for desktop integration. That record's author should reconcile the wording.

## Implementation

We will build the desktop window as a React shell at the app origin that hosts the packaged user documentation in a cross-origin iframe. A right-side log flyout and a bottom two-tab terminal panel sit alongside the iframe. User-approved additions (2026-10-04):

- Enter restarts a session that has exited.
- Desktop-host events appear in the log flyout.
- Ctrl+= / Ctrl+- / Ctrl+0 zoom the documentation only.
- The layout is remembered between launches.

**Layout.**

- The documentation fills the area above the panel, and the iframe starts on the index of the preferred language.
- The flyout slides over the documentation only, from the right, so the terminal stays visible. It defaults to 26rem wide, can be resized from 18rem up to 70 percent of the width, and covers the whole documentation width on narrow windows.
- The bottom panel is a tab strip plus terminals:
  - tabs in the spec's order, Python first, then TUI; TUI is active on first launch
  - default height 40 percent, resizable with a keyboard-operable separator, collapsible to the strip
  - the documentation keeps at least 10rem, and a terminal at least four rows
- The shell follows the documentation's theme (`auto`, `light`, `dark`), which the bridge reports. Shell tokens are generated from the documentation palette declared in `docs/conf.py`, not copied. Terminals use a bundled JetBrains Mono.

**Packaging and origins** (hypothesis: exact paths may change during the technical review):

- The documentation ships under `P/docs/user/` in the owner's published layout, with English at the top and es/ca/hu under `<lang>/`. The language switcher (`docs/_templates/cadrumo-language-switcher.html:19`) depends on that layout. A docs manifest lists the languages, the entry path for each, a sha256 inventory and the hashes of executing inline scripts. The shell takes entry paths from `desktop_environment` and never builds them itself. The packaging step refuses missing Pagefind output and any remote reference.
- Documentation is served read-only through the `cadrumo-docs` scheme with path containment, a closed MIME table and its own CSP:
  - `script-src 'self' 'wasm-unsafe-eval'` plus the manifest hashes
  - `connect-src 'self'`
  - `form-action 'self'`
  - `frame-ancestors` set to the shell origin
- The shell CSP changes `frame-src` to the documentation origin.
- A desktop documentation flavor:
  - removes the MathJax CDN reference
  - disables hoverxref's remote embed
  - exposes the search-palette opener
  - loads the bridge script before `cadrumo-docs.js`

**Bridge protocol.** `window.postMessage` with an exact origin and source check on both sides, envelope `{channel: "cadrumo-desktop", version: 1, type}`.

documentation to shell:
- `ready {url, title, lang, theme}`
- `location {url, title}`
- `theme {theme}`
- `shortcut {id}`
- `open-external {url}`
- `context-menu {x, y, selection, link}`, where selection is at most 65,536 characters

shell to documentation:
- `keymap {chords}`, matched on `KeyboardEvent.code`
- `command {name: back | forward | open-search}`
- `zoom {factor 0.5 to 2.0}`

**Host IPC** (field names may change during the technical review; the semantics are committed):

- Terminals, at most one live session per kind (`python`, `tui`), over Tauri Channels:
  - `terminal_open` returns a session and streams raw output plus `started`, `exited` and `failed` events
  - `terminal_write` takes a raw body
  - `terminal_ack` is credit backpressure: pause at 512 KiB unacknowledged, resume below 128 KiB
  - `terminal_resize`
  - `terminal_close` settles before it returns
  - The Python session is the packaged interpreter with no arguments and the TUI's child environment, started in the user's home directory. That is only allowed once the projected storage root is pinned in the child environment (see Constraints). Before that, both kinds start in the same working directory. The interactive interpreter never starts inside the storage root. A relative write such as `open("notes.csv", "w")` would otherwise land a plaintext file inside the custody tree. Private data enters that tree only through approved encrypted custody.
- Logs:
  - `logs_subscribe` delivers batches of at most ten per second, starting with a 5,000-record backlog from a 10,000-record ring
  - each record carries `seq`, `source` (`python` or `host`), the raw timestamp, a parsed timestamp or null, a level or null, a logger or null, the message, a detail (continuation lines) or null, and a host process
  - each batch carries the source state
  - Rust receives the line format from the Python environment query and keeps no copy of its own.
- Shell commands:
  - `desktop_environment`: output language and documentation origin and languages
  - `open_external`
  - `shell_clipboard_read` and `shell_clipboard_write` for text, and `shell_context_menu` for native menus, each a token-checked app command that wraps the plugin or menu Rust API. The menu either returns the chosen item, or returns at once and delivers the selection later under a popup id. That depends on whether the menu library reports a dismissal. The shell needs no dismissal signal, so either form works.
  - window state, Rust-only, with no JavaScript command
  - WebView2 browser accelerator keys and default context menus are disabled.

**Keymap** (shell-owned; reserved from xterm through `attachCustomKeyEventHandler`; relayed from the documentation through the bridge):

| Chord | Action | Scope |
|---|---|---|
| Ctrl+Shift+L | Toggle the log flyout | Global |
| Ctrl+` (physical Backquote) | Toggle the panel and focus the active terminal | Global |
| Ctrl+Shift+1 / Ctrl+Shift+2 | Python tab / TUI tab, with focus | Global |
| Ctrl+Shift+F | Focus the documentation and open its search palette | Global |
| Alt+Left / Alt+Right | Documentation back / forward | Documentation or flyout |
| Ctrl+= / Ctrl+- / Ctrl+0 | Documentation zoom | Documentation or flyout |
| Ctrl+Shift+C / Ctrl+Shift+V | Copy / paste | Terminal |
| Escape | Close the flyout | Flyout |
| Enter after exit | Start the session again | Exited terminal |

**Context menus.** The shell describes each menu and its localized labels. A token-checked host command shows it natively at coordinates relayed from the iframe and returns the chosen item. When a terminal application has mouse tracking on, Shift+right-click opens the menu.

| Target | Items |
|---|---|
| Documentation | Copy; Copy link address; Back; Forward |
| Terminal | Copy; Paste; Select all |
| Log line | Copy line; Copy visible; Show only this logger; Show only this level or worse |

**Persistence.**

- Window size, position and maximized state go through the window-state plugin.
- Panel height, collapsed state, active tab, flyout open and width, and documentation zoom go in shell localStorage.
- Every read is guarded, so the layout falls back to defaults.

## Rationale

The iframe shell is the only option that meets three needs together:

- terminal sessions and the flyout persist while the documentation navigates
- overlays compose with the documentation
- documentation scripts are kept from IPC

Origin separation does the third job without the unstable multi-webview feature. Serving from package files follows the size and file count in `2026-10-04-desktop-shell-reference`.

A shell-owned keymap made of Ctrl+Shift chords and the physical Backquote key avoids every key the TUI and REPL bind. Pushed channels with credit backpressure replace polling without dropping output.

## Consequences

**Benefits.**
- The documentation becomes the window's primary surface, with offline search in four languages.
- Terminals no longer poll.
- Logs from every Python process on the storage root that logs through `configure_logging` show in one place. That includes the runtime (`src/cadrumo/entrypoints/runtime/main.py:53`).

**Accepted costs.**
- An installed package grows by about 450 MB and 63,000 files across four languages, measured at packaging.
- The documentation needs a desktop build flavor.
- Log records can't name the Python process that wrote them until a structured log sink is decided separately.

**Reconsider if:**
- package size or file count proves unacceptable for installation
- Tauri stabilizes multi-webview layout
- the runtime-management ruling places runtime state or authentication prompts in the shell

**Seams kept but not built.** These would need a runtime-manager decision and the user's approval:
- a status slot in the tab strip, fed only through the runtime manager's own local IPC and never from the runtime endpoint
- a host command that asks the single runtime-manager instance to show its own UI, starting, stopping and authenticating nothing
- a close prompt keyed to a fact the TUI reports, that it has an open interaction, rather than to runtime state

The runtime-control UI in `2026-10-03-application-packaging-adr` moves to the runtime manager, not to `cadrumo.exe`.

Acceptance would not mean that any part of this is implemented.
