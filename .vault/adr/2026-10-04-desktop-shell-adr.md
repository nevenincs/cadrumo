---
tags:
  - '#adr'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:fbb4c71266c60a8e81f576dbbf740ccc5170849deebb9d23415e4d9f9449477c'
related:
  - "[[2026-10-04-desktop-shell-reference]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
---

# `desktop-shell` adr: `Desktop shell` | (**status:** `accepted`)

## Problem Statement

The user's 2026-10-04 frontend spec replaces the fullscreen terminal in `cadrumo.exe` with a window built around the bundled user documentation. The docs must be readable, browsable and searchable. The window also gives access to the Cadrumo TUI, a system console and a Python shell, each with the Cadrumo environment, and to the aggregated backend logs. The user refined the layout the same day after reviewing a first prototype, and the record below reflects that layout.

This needs a decision now because it fixes several things at once:

- how documentation is packaged and served under a strict webview CSP
- the IPC and cross-origin message protocols between the shell, the documentation and the Rust host
- the keymap shared with the TUI and the shells
- how far the shell may reach into backend state

Evidence is in `2026-10-04-desktop-shell-reference`.

## Considerations

- The window CSP admits only `'self'`, so documentation, search, fonts, icons and scripts must all be local (`2026-10-04-desktop-shell-reference`).
- The documentation set is about 435 MB in about 63,000 files across four languages. Every file can't be compiled into the binary.
- The documentation runs third-party JavaScript (jQuery, Furo, mermaid, Pagefind). Tauri IPC must stay out of its reach.
- The TUI and the shells own F1 to F10, Ctrl+P, Ctrl+Q, Ctrl+C, Ctrl+K, Escape and plain keys. WebView2 accelerators collide with several of these.
- The shell grants no authority and adds no CLI semantics. Runtime launch, supervision, availability and authentication belong to the runtime and to the per-user runtime manager (`2026-10-04-runtime-manager-architecture-adr`). Runtime management is a required dependency of the desktop application, because MCP clients can't connect otherwise. `2026-10-03-runtime-without-service-manager-adr` is interim, so this record ties its constraint to ownership, not to that record.
- Admitted work is owned by the runtime and survives the client disconnecting (`2026-09-26-mcp-purpose-authentication-adr`). Interaction bearers are local to one process. An operation waiting on review or confirmation from a TUI that has exited settles under the runtime's rules, by refusal or expiry, and a restarted TUI can't answer it.
- The storage root is pinned by the host from the canonical definition in `2026-10-04-canonical-environment-adr`. Children inherit it whatever their working directory.
- The user removed earlier unapproved landing content. Anything outside the spec, the user's layout direction and the additions approved on 2026-10-04 needs the user's approval.
- Localized chrome uses the informal singular. It comes from the canonical locale catalogues, with no parallel translation table.

## Considered options

- **React shell with a cross-origin documentation iframe:** chosen. Terminal sessions survive documentation navigation, docs and TUI can share the main area, overlays such as the palette compose normally, and origin separation is the first layer of keeping documentation scripts from IPC.
- **Documentation as the top-level page, with terminals in native child webviews:** rejected as the primary design, and kept as the contingency if the iframe isolation proof fails. It depends on Tauri's unstable multi-webview feature, nothing can overlay the documentation, and keyboard focus between webviews is fragile.
- **Documentation embedded in `frontendDist`:** rejected. It means 63,000 files compiled into the binary, and a Rust rebuild for every documentation edit.
- **Documentation served from the development docs server (port 8788):** rejected. It isn't a packaged artifact, and dev and package would behave differently.
- **A right-side log flyout with two bottom terminal tabs:** the first prototype. The user replaced it with a single bottom panel that also holds the logs, and moved the TUI next to the docs.

## Constraints

- The documentation origin gets no IPC, plugin or capability. The pinned crates can't enforce this on their own:
  - Tauri 2.12.1 treats every registered custom scheme as a local origin.
  - On Windows, wry injects every initialization script into subframes too, ignoring a main-frame-only flag. Tauri's own internals, IPC script and invoke key therefore reach the documentation frame.
  - The channel fetch command is exempt from the ACL and uses sequential ids.

  The refusal therefore belongs to the application:
  - **Token minting.** The host mints a per-launch token from at least 32 CSPRNG bytes and never logs or persists it.
  - **Self-gated script.** The script carrying the token checks at runtime that it is the top frame on the shell origin. It exposes the token once, through a getter that deletes itself. The shell keeps the token in module scope.
  - **Token checks.** Every app command checks the token in constant time and refuses a mismatch with `invalid_arguments`.
  - **Shell rules.** The shell never posts the token to the iframe or puts it in a URL or storage, and the bridge envelope never carries it.
  - **Channel delivery.** A channel interceptor delivers channel data into the top document only. Nothing waits in the fetch queue.
  - **Documentation CSP.** Every documentation response carries `connect-src 'self'`, which blocks the IPC fetch transport.
  - **No plugin JavaScript.** No plugin JavaScript command is granted to the webview. The opener, clipboard and menu are reached only through token-checked app commands, and the opener's click interception is off.
  - **Adversarial proof.** The packaged end-to-end test proves from inside the documentation frame that invoke, the IPC fetch, postMessage IPC, and fetching or consuming channel data are all refused.
  - **Contingency.** If any delivery is shown, the documentation moves to a separate webview (Tauri multi-webview) in its own decision.
- The host requires a minimum WebView2 runtime that supports iframe and worker request interception and the settings it disables. It probes the runtime at startup and refuses with a typed error. WebView2 settings go through the platform crate.
- Origins are computed at runtime: http or https per the platform's scheme setting, the custom-scheme form on Linux, and the dev server URL in development.
- The frontend bundle contains no location, path, origin or environment variable name. Every runtime value comes from `desktop_environment`. The only build-time inputs are the dev-server host and ports from the canonical definition.
- PTY bytes never enter diagnostics, host logs or the log view. The log view shows host events and Python log records only.
- Nothing remote loads in the webview. External https and mailto links open in the system browser through a host command that revalidates the URL. Every other scheme is refused. The shell acts on a bridge `open-external` only while `navigator.userActivation.isActive`, and under a rate limit.
- The shell never captures F1 to F10, Ctrl+P, Ctrl+Q, Ctrl+C, Ctrl+K, Escape or plain keys while a terminal has focus.
- The log view keeps "available", "missing" and "unreadable" sources distinct from an empty list. It only reads the log and never truncates, rotates or deletes it.
- The log reader expects rotation to be late, skipped or racing, because several processes share one `RotatingFileHandler` file and a rename on Windows fails while another process has the file open. It never infers that a process exited from a file event. It also doesn't assume that profile workers log to this file.
- `source` on a log record is an open enumeration. A later runtime-manager source must not break the shell.
- Terminal output is never dropped. Backpressure pauses the PTY reader instead.
- The shell holds no runtime connection and no runtime authority. It never opens the runtime endpoint, and it shows no runtime availability, authentication request, timeout or control, with three exceptions from `2026-10-04-application-sign-in-adr`:
  - the sign-in view's signed-in state, as `aeat config sign-in-status` reports it
  - that view's typed refusals
  - the manager-start path offered when the runtime is unavailable
- Following `2026-10-04-runtime-manager-architecture-adr` (desktop-shell plan S12), the desktop may start a missing `cadrumo-manager` by shell dispatch (Explorer on Windows, LaunchServices on macOS), never as its own child. It may ask the manager to `reveal` its own UI over the manager IPC. It never starts, stops or authenticates the runtime.
- The desktop shell owns the cross-version GUI single instance:
  - The lock is per user, keyed by identity family and channel.
  - A second GUI launch hands its activation to the open window and exits 0.
  - A newer version launched while an older window is open hands activation to that window, and the user finishes the switch by closing the old window.
  - The headless CLI passthrough is exempt.
- The shell hosts the application sign-in view of `2026-10-04-application-sign-in-adr`. It submits only through its dedicated host command to the canonical CLI login, and holds no session, receipt or credential. The runtime's profile worker still launches the Cl@ve browser, and approval prompts still belong to the TUI.
- The shell never caches, forwards or persists session, lease, receipt or credential material between TUI processes. Restarting a session starts a new process that goes through admission again.
- No shell or host copy says that work completes after a terminal closes or the window closes.
- The host adds no storage-root, log-directory or other Settings variable to its child processes beyond the pinned set `2026-10-04-canonical-environment-adr` declares. The host, every terminal kind and the CLI passthrough resolve the same root whatever their working directory, and a regression test in a relocated packaged layout proves it (desktop-shell plan S02).
- Interactive shells (`console`, `python`) never start inside the storage root. A relative write such as `open("notes.csv", "w")` would otherwise land a plaintext file inside the custody tree. Private data enters that tree only through approved encrypted custody.
- Shell settings are frontend preferences only. They never write product Settings or reach the backend.
- This record replaces these items in `2026-10-03-application-packaging-adr`: the separate Tauri `index.html` landing page, `docs/index.html` exposed through asset integration, and the runtime-control UI listed for desktop integration, which moves to the runtime manager. That record's author reconciles the wording.

## Implementation

We will build the desktop window as a React shell at the app origin. A left icon rail sits beside a main area that splits the packaged user documentation, in a cross-origin iframe, with the Cadrumo TUI. A single toggleable bottom panel holds three tabs: Console, Python and Logs. Approved additions (2026-10-04):

- Enter restarts a session that has exited.
- Desktop-host events appear in the log view.
- Ctrl+= / Ctrl+- / Ctrl+0 zoom the documentation only.
- The layout is remembered between launches.

**Layout** (user direction 2026-10-04, prototyped and reviewed):

- **Rail.** A collapsed, icon-only vertical toolbar with one tab stop and arrow-key movement. From the top:
  - Search, which opens the palette
  - Docs home
  - TUI, which toggles the TUI pane
  - Console, Python and Logs. Each opens the bottom panel on its tab, and clicking the active one collapses the panel. Logs carries an error-count badge.
  - Settings at the bottom

  Every rail item shows a tooltip with its label and shortcut.
- **Main area.** The documentation and the TUI, side by side or stacked, with either pane first. The split ratio is remembered as a share, and a keyboard-operable separator resizes it. Hiding the TUI gives the documentation the whole area while the TUI session keeps running. Swapping, reorienting and hiding never remount the documentation frame or a terminal. Both panes have a slim header, because the user asked on 2026-10-04 for a maximize control beside the swap, split and close controls on the docs, the TUI and the bottom panel. The documentation pane's header carries maximize, swap and orientation, with no close. The TUI pane's header adds its status and hide. Double-clicking a header toggles maximize. Maximizing an area hides the others without remounting them, and reaching for another area restores the layout. The iframe starts on the entry of the preferred language.
- **Bottom panel.** One element with the Console, Python and Logs tabs. Its height is remembered as a share of the window and resized with a keyboard-operable separator. Collapsing it hides it entirely. The documentation keeps at least 200 px, and the panel at least 140 px.
- **Palette.** Ctrl+K (⌘K on macOS) opens one palette for the whole window. It lists matching shell actions with their shortcuts and documentation results from the docs frame's search, grouped by kind: terms, casillas, CLI commands and pages. Selecting a documentation result navigates the documentation. The docs' own Ctrl+K palette and sidebar trigger are relayed to this palette, so the app has one search.
- **Settings.** A popover from the rail. It holds:
  - appearance: follow the documentation, light or dark
  - terminal colours: match the appearance, or always dark
  - the split's orientation and which pane comes first
  - terminal text size
  - reset layout
- **Theme.** Shell tokens are generated from the documentation palette declared in `docs/conf.py`, not copied. A forced appearance is pushed to the documentation. Terminals use a bundled JetBrains Mono, and icons are a bundled inline set.

**Shared primitives.** The shell is built from:

- one action registry, which every keymap chord, palette entry, rail tooltip and menu shortcut is derived from
- a context-menu model rendered natively by the host
- the palette
- a split
- the log view
- the rail
- the icon set

A chord or label is declared once, in the registry.

**Packaging and origins.**

- The documentation ships under `P/docs/user/` in the owner's published layout, with English at the top and es/ca/hu under `<lang>/`. The language switcher (`docs/_templates/cadrumo-language-switcher.html:19`) depends on that layout. A docs manifest lists the languages, the entry path for each, a sha256 inventory and the hashes of executing inline scripts. The shell takes entry paths from `desktop_environment` and never builds them itself. The packaging step refuses missing Pagefind output and any remote reference.
- Documentation is served read-only through the `cadrumo-docs` scheme with path containment, a closed MIME table and its own CSP:
  - `script-src 'self' 'wasm-unsafe-eval'` plus the manifest hashes. Pagefind needs only `'wasm-unsafe-eval'`, because it instantiates WebAssembly from bytes and runs a classic worker from 'self' with no blob URLs.
  - `connect-src 'self'`
  - `X-Content-Type-Options: nosniff`
  - `form-action 'self'`
  - `frame-ancestors` set to the shell origin
- The shell CSP changes `frame-src` to the documentation origin.
- A desktop documentation flavor:
  - removes the MathJax CDN reference
  - disables hoverxref's remote embed
  - loads the bridge script before `cadrumo-docs.js`

**Bridge protocol.** `window.postMessage` with an exact origin and source check on both sides, envelope `{channel: "cadrumo-desktop", version: 1, type}`.

documentation to shell:
- `ready {url, title, lang, theme}`
- `location {url, title}`
- `theme {theme}`
- `shortcut {id}`. This includes `palette.open`, relayed for Ctrl+K inside the docs and for a click on the docs' own search trigger, which is intercepted in the capture phase.
- `open-external {url}`
- `context-menu {x, y, selection, link}`, where selection is at most 65,536 characters
- `search-results {id, results}`. Each result is `{kind, title, url, excerpt, ranges}`. The excerpt is plain text with match ranges, never HTML, and only same-origin documentation URLs are allowed. Results are ranked by the docs search controller.

shell to documentation:
- `keymap {chords}`, matched on `KeyboardEvent.code`
- `command {name: back | forward | home | navigate, url?}`. `navigate` is refused for any URL outside the documentation origin. `home` goes to the manifest entry of the active language.
- `search {id, query, limit}`, with a bounded query and limit, and at most one request in flight per id
- `zoom {factor 0.5 to 2.0}`

**Host IPC** (the semantics are committed; field names follow the technical plan):

- Terminals, at most one live session per kind (`console`, `python`, `tui`). Every command carries the token.
  - `terminal_open {kind, cols, rows, output}` returns a session. It streams one Tauri Channel of tagged frames, data plus `started`, `exited` and `failed`, so `exited` can never overtake output.
  - `terminal_write` takes a raw body, or a bounded JSON byte array once Tauri has fallen back to postMessage. Headers are sent as a plain object. The shell retries `queue_full`.
  - `terminal_ack` reports a cumulative offset, as credit backpressure: pause at 512 KiB unacknowledged, resume below 128 KiB.
  - `terminal_resize`
  - `terminal_close` settles before it returns.
  - A reload of the top frame settles or replaces every session.
  - `console` is the platform's interactive system shell: PowerShell 7, falling back to Windows PowerShell 5.1, on Windows, and the account's login shell on Linux. It's resolved absolutely, never through PATH from the working directory, with package `bin/` first on PATH.
  - `python` is the packaged interpreter with no arguments.
  - Both start in the user's home directory with the same child environment as the TUI. The TUI starts in the pinned storage root.
- Logs:
  - `logs_subscribe` delivers batches of at most ten per second, starting with a 5,000-record backlog from a 10,000-record ring
  - each record carries `seq`, `source`, the raw timestamp, a parsed timestamp or null, a level or null, a logger or null, the message, a detail (continuation lines) or null, and a host process
  - each batch carries the source state
  - Rust receives the line format from the Python environment query and keeps no copy of its own.
- Shell commands:
  - `desktop_environment`: output language and documentation origin and languages
  - `open_external`, Rust-only through the opener
  - `shell_clipboard_read` and `shell_clipboard_write` for text
  - `shell_context_menu {items, x?, y?}`, which returns `{chosen: id | null}`:
    - Synchronous: the native popup blocks until it closes, and a main-thread sentinel resolves a dismissal as null.
    - Pointer-opened menus omit x and y, so the menu opens at the cursor.
    - The keyboard menu key passes a logical position in shell CSS pixels: the iframe rect, plus its border, plus the relayed client coordinates, with no device-pixel scaling.
    - Item ids are namespaced by the host.
  - window state, Rust-only, with no JavaScript command
  - WebView2 browser accelerator keys and default context menus are disabled.
- Browser-mode tests of the shell use a stand-in documentation origin.

**Keymap** (shell-owned, declared in the action registry, reserved from xterm through `attachCustomKeyEventHandler`, and relayed from the documentation through the bridge). "Mod" is Ctrl, or ⌘ on macOS. "Not in a terminal" means the chord passes through to a focused terminal.

| Chord | Action | Scope |
|---|---|---|
| Mod+K | Open or close the palette | Not in a terminal |
| Mod+Shift+K | Open or close the palette | Everywhere |
| Mod+Shift+T | Show or hide the TUI | Everywhere |
| Ctrl+` (physical Backquote) | Show or hide the bottom panel | Everywhere |
| Mod+Shift+1 / 2 / 3 | Console / Python / Logs tab | Everywhere |
| Mod+Shift+L | Logs tab | Everywhere |
| Mod+, | Settings | Not in a terminal |
| Alt+Home | Docs home | Documentation or chrome |
| Alt+Left / Alt+Right | Documentation back / forward | Documentation or chrome |
| Mod+= / Mod+- / Mod+0 | Documentation zoom | Documentation or chrome |
| Mod+Shift+C / Mod+Shift+V | Copy / paste | Terminal |
| Escape | Close the palette, a menu or settings | That surface |
| Enter after exit | Start the session again | Exited terminal |

**Context menus.** The shell describes each menu and its localized labels. A token-checked host command shows it natively and returns the chosen item, or null when the menu is dismissed. When a terminal application has mouse tracking on, Shift+right-click opens the menu.

| Target | Items |
|---|---|
| Documentation | Copy; Copy link address; Back; Forward; Docs home |
| Console and Python | Copy; Paste; Select all; Clear |
| TUI | Copy; Paste; Select all |
| Log line | Copy line; Copy visible; Show only this logger; Show only this level or worse |

**Persistence.**

- Window size, position and maximized state go through a host window-state module. It stores them as `window-state.json` in the declared webview location, restores them on window ready within the visible monitors, and saves them atomically on close, with no JavaScript command. The window-state plugin was set aside because it creates an undeclared `%APPDATA%` directory, which `2026-10-04-canonical-environment-adr` forbids.
- Settings, the split ratio, whether the TUI is shown, panel open, panel share, active tab and documentation zoom go in shell localStorage.
- Every read is guarded, so the layout falls back to defaults.

## Rationale

The iframe shell is the only option that meets three needs together:

- terminal sessions persist while the documentation navigates
- the documentation and the TUI share the main area, with overlays such as the palette composing over both
- documentation scripts are kept from IPC

On Windows the pinned crates reach subframes, so origin separation alone doesn't do the third job. It is done by the self-gated token, top-document channel delivery, and the documentation CSP, and the packaged test proves it adversarially. Separate webviews remain the fallback if that proof fails. Serving from package files follows the size and file count in `2026-10-04-desktop-shell-reference`.

The user's layout puts the two most useful surfaces, the documentation and the TUI, side by side. It folds the shells and the logs into one panel, so the window has a single secondary surface instead of a flyout plus a panel. A shell-owned keymap made of Mod+Shift chords and the physical Backquote key avoids every key the TUI and the shells bind. One action registry keeps chords, labels and menus consistent. Pushed channels with credit backpressure replace polling without dropping output.

## Consequences

**Benefits.**
- The documentation is the window's primary surface, with offline search in four languages, reachable from one palette.
- The documentation and the TUI can be read and used at the same time.
- Terminals no longer poll.
- Logs from every Python process on the storage root that logs through `configure_logging` show in one place. That includes the runtime (`src/cadrumo/entrypoints/runtime/main.py:53`).

**Accepted costs.**
- An installed package grows by about 450 MB and 63,000 files across four languages, measured at packaging.
- The documentation needs a desktop build flavor and bridge additions for search and navigation.
- Log records can't name the Python process that wrote them until a structured log sink is decided separately.
- A third terminal kind adds a platform shell resolution to the host.

**Reconsider if:**
- package size or file count proves unacceptable for installation
- Tauri stabilizes multi-webview layout
- the runtime-manager decision places runtime state or authentication prompts in the shell. This trigger has been exercised: `2026-10-04-application-sign-in-adr` placed the sign-in view in the shell.

**Seams kept but not built.** These need the user's approval:
- a status slot fed only through the runtime manager's own local IPC, never from the runtime endpoint
- a rail or palette action that asks the manager to `reveal` its UI, which the constraint above allows but the user hasn't asked for
- a close prompt keyed to a fact the TUI reports, that it has an open interaction, rather than to runtime state

Acceptance (user, 2026-10-04) doesn't mean that any part of this is implemented.
