---
tags:
  - '#adr'
  - '#desktop-shell'
date: '2026-10-04'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:55c22caa722b1716b6419df1740fd756252748d56c99fbbdc392458a1fc9d4ee'
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
  - '[[2026-10-15-language-sync-reference]]'
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
- Nothing remote loads in the webview. External https and mailto links open in the system browser through a host command that revalidates the URL. A well-formed `cadrumo://profiles/{id}/{page}` link opens that page in the window's own TUI (amendment of 2026-10-22) and never reaches the browser. Every other scheme is refused. The shell acts on a bridge `open-external` only while `navigator.userActivation.isActive`, and under a rate limit.
- The shell never captures F1 to F10, Ctrl+P, Ctrl+Q, Ctrl+C, Ctrl+K, Escape or plain keys while a terminal has focus.
- The log view keeps "available", "missing" and "unreadable" sources distinct from an empty list. It only reads the log and never truncates, rotates or deletes it.
- The log reader expects rotation to be late, skipped or racing, because several processes share one `RotatingFileHandler` file and a rename on Windows fails while another process has the file open. It never infers that a process exited from a file event. It also doesn't assume that profile workers log to this file.
- `source` on a log record is an open enumeration. A later runtime-manager source must not break the shell.
- Terminal output is never dropped. Backpressure pauses the PTY reader instead.
- The shell holds no runtime connection and no runtime authority. It never opens the runtime endpoint, and it shows no runtime availability, authentication request, timeout or control, with these exceptions from `2026-10-04-application-sign-in-adr`:
  - the sign-in view's signed-in state, as `cadrumo-runtime config sign-in-status` reports it
  - that view's typed refusals
  - the manager-start path offered when the runtime is unavailable
  - by that record's amendment of 2026-10-06, the profiles of the sign-in view: their labels and which is selected, as `aeat config profile list` reports them, the profile a sign-in names, and the creation of a profile through the canonical CLI
- Following `2026-10-04-runtime-manager-architecture-adr` (desktop-shell plan S12), the desktop may start a missing `cadrumo-manager` by shell dispatch (Explorer on Windows, LaunchServices on macOS), never as its own child. It may ask the manager to `reveal` its own UI over the manager IPC. It never starts, stops or authenticates the runtime.
- The desktop shell owns the cross-version GUI single instance:
  - The lock is per user, keyed by identity family and channel.
  - A second GUI launch hands its activation to the open window and exits 0.
  - A newer version launched while an older window is open hands activation to that window, and the user finishes the switch by closing the old window.
  - The headless CLI passthrough is exempt.
- The shell hosts the application sign-in view of `2026-10-04-application-sign-in-adr`. It submits only through its dedicated host command, which signs the selected profile in through the window's person hold child and another profile through the canonical CLI login; the shell process holds no session, receipt or credential. The runtime's profile worker still launches the Cl@ve browser, and approval prompts still belong to the TUI.
- The shell never caches, forwards or persists session, lease, receipt or credential material between TUI processes. Restarting a session starts a new process that goes through admission again.
- No shell or host copy says that work completes after a terminal closes or the window closes.
- The host adds no storage-root, log-directory or other Settings variable to its child processes beyond the pinned set `2026-10-04-canonical-environment-adr` declares. The host, every terminal kind and the CLI passthrough resolve the same root whatever their working directory, and a regression test in a relocated packaged layout proves it (desktop-shell plan S02).
- Interactive shells (`console`, `python`) never start inside the storage root. A relative write such as `open("notes.csv", "w")` would otherwise land a plaintext file inside the custody tree. Private data enters that tree only through approved encrypted custody.
- Shell settings are frontend preferences only. They never write product Settings or reach the backend.
- This record replaces these items in `2026-10-03-application-packaging-adr`: the separate Tauri `index.html` landing page, `docs/index.html` exposed through asset integration, and the runtime-control UI listed for desktop integration, which moves to the runtime manager. That record's author reconciles the wording.

Amendment approved 2026-10-07 under the user's environment-readiness instruction: the earlier requirement for console and Python REPL to start in the generic user home is replaced by a dedicated console workspace declared in the canonical storage taxonomy beneath the resolved CADRUMO root. This workspace is for operator-authored scripts and scratch files, not encrypted profile custody. All desktop terminal kinds use this workspace and the same pinned storage/environment and bundled command search path. Standalone command invocations retain the caller's cwd for relative arguments. Authentication still uses native peer verification and the existing profile receipt flow; profile identifiers or credentials are not conveyed through new environment variables. Runtime start/supervision remains with the manager. This amendment also supersedes the home-cwd sentence in the terminal implementation specification below; all other shell authority constraints stand.

### 2026-10-09 authorized scoped installation command

The operator authorizes token-checked manager installation for user/machine scope and missing-installation recovery under 2026-10-09-desktop-service-installation-adr. This extends the shell's manager-start surface to verified native installation followed by shell dispatch of the published manager. Machine scope elevates the installer only. Runtime transport, profile and supervision authority remain excluded.

### 2026-10-10 authorized startup ownership and optional-installation amendment

Accepted under the user's explicit instruction that installation is optional, admin installation supplies a machine-start platform manager, user installation supplies login startup, and every running Cadrumo GUI must establish runtime supervision. This supersedes the earlier exclusions of desktop-owned supervision and Windows SCM hosting for this scope. A boot-time Windows service is a lifecycle broker only: it launches and watches per-user managers using genuine user logon tokens; it never owns profile credentials or runs a taxpayer runtime as SYSTEM. User-only installation retains unprivileged login startup. Cadrumo embeds the existing manager supervision core as a fallback when no installed session manager owns supervision, with the same native ownership lock, runtime start claim, process identity verification, heartbeat/recovery and authenticated client readiness. Existing installed managers retain ownership; a running GUI watches their liveness and takes over after ownership is released. Installation registration, dispatch acknowledgement, a PID or a supervisor ready line alone never establishes application readiness. CLI, TUI and MCP remain connect-only. Build and command acceptance exercise the shipped Cadrumo startup path and fail when supervision or real native IPC readiness fails. No development-host boot/login registration is required to test GUI fallback. Real installed boot/login acceptance remains separately reported until exercised on a disposable host. Detailed prior evidence: 2026-10-09-runtime-process-lifecycle-audit.

### 2026-10-12 desktop without bundled documentation

Operator direction 2026-10-12: the documentation is not a critical component; the Tauri application must be fully functional with or without it, and must understand that the documentation is not bundled and behave accordingly. This amends the window "built around the bundled user documentation" so that the documentation is optional.

- The package manifest's `user_docs` statement governs the documentation state; file presence alone never decides. `bundled: false` is reported as `notBundled`. A bundled tree, media-type table or documentation policy that cannot be admitted, or a manifest with no statement, is recorded as a diagnostic failure and reported as `unavailable`. None of these refuses the launch.
- Whenever no documentation is served, the host registers the documentation scheme so that it refuses every request under the closed policy, and `desktop_environment` reports the state instead of an origin and languages. Admission of a served tree keeps its existing checks. The WebView2 interface requirement and every shell authority constraint above still apply.
- The shell keeps every other function unchanged: the TUI, console and Python terminals, logs, calendar, sign-in, manager start, settings and palette actions. The documentation pane states that this copy was built without the documentation, or that it could not be opened, instead of loading a frame; documentation search and the documentation language list are empty. The adversarial isolation proof applies whenever documentation is bundled.

### 2026-10-12 sign-in view on every loss of sign-in

The owner ruled first-hand on 2026-10-12 that Cadrumo is a GUI application with only one active, signed-in profile, and that the shell shows the sign-in screen when the profile sign-in times out, goes inactive, or no profile exists (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`). This amends when the sign-in view of `2026-10-04-application-sign-in-adr` is shown. Before, it was shown only before the TUI pane starts while the active profile has no live sign-in.

- The shell withholds the TUI and shows the sign-in view whenever the sign-in expires by its idle or absolute deadline, is signed out, is locked, or is lost to lock-down, and whenever no profile exists.
- It learns of each from the runtime's pushed session events where they reach it, and otherwise from the `sign-in-status` read it already polls. It never infers a sign-in from its own state.
- A locked profile shows the sign-in view. Whether resuming a locked profile happens in the view or is handed to the TUI's flow stays as `2026-10-04-application-sign-in-adr` rules.
- The view offers another profile only while signed out, because only one profile is signed in at a time.
- The shell still holds no session, receipt, credential or runtime connection. It never signs in on an agent's behalf.

## Implementation

### Amendment 2026-10-15: canonical language synchronization

Accepted under the user's explicit request for shared language switching in Settings, Cmd+K, documentation and TUI. The blanket frontend-only shell-settings constraint is amended for language only: the shell may read, write and observe the canonical authenticated profile preference through narrow token-checked host commands and the verified person transport. It receives no new custody or credential authority. Profile mutations retain registered-operation validation and record preconditions; a notification is an invalidation cue, never authority or a persisted substitute. Signed-out choices remain transient and cannot write a profile or its hint. Explicit per-invocation CLI overrides remain supported.

The existing documentation bridge gains a bounded supported-language request and completion instruction under the same exact origin/source checks. One subscribed frontend controller updates chrome, projections and documentation; profile-scoped runtime notices refresh mounted TUI presentation without discarding staged work. Background observation must not extend person activity. This scoped exception supersedes only earlier statements excluding backend language preferences. Evidence: `2026-10-15-language-sync-reference`.

The installed interactive TUI follows the canonical profile language ahead of inherited environment or Settings language defaults. Those defaults remain its fallback when the profile has no preference. This precedence is scoped to the interactive host lifetime, resets when it exits and does not change ordinary CLI per-invocation overrides. The separate TUI module grammar accepts no language launch flag; no supported explicit TUI flag is removed. This closes the observed case where the desktop adopted a profile change while an inherited setting kept the TUI in its prior language.

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
  - One bottom-panel toggle, carrying the log error-count badge. It opens the remembered Console, Python or Logs tab and collapses the panel when open; tab selection remains inside the panel and in the existing shortcuts and palette actions.
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
  - Rust receives the canonical line format from the build-generated Python defaults on the Windows default-settings path, or from the Python environment query on fallback paths. It keeps no independently authored copy.
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
- Settings and presentation choices go in shell localStorage: pane visibility, active page, maximized pane, split ratios, panel visibility and tab, documentation zoom, calendar face, profile section/filter/disclosures and the chosen minimum log level. A fresh layout shows Profile and the agent where available; the TUI is closed until requested. Existing explicit saved pane choices are retained. See the 2026-10-21 amendment.
- Every read is guarded, so the layout falls back to defaults.

### Embedded terminal appearance amendment (2026-10-07)

Authorized by the user's request that desktop theme switching restyle the TUI and shells. Source inspection found the TUI pane pinned to DARK_TERMINAL and Textual themes emitting fixed RGB colors (`native/desktop/frontend/src/App.tsx`, `src/cadrumo_runtime/host/frontend/tui/components/theme.py`). Changing xterm's background cannot recolor those cells.

The dedicated desktop TUI uses native ANSI color roles backed by desktop-owned light/dark Cadrumo palettes. Its launch identifies the terminal through TERM_PROGRAM=cadrumo; this is terminal capability metadata, alongside TERM and COLORTERM, not a product Settings variable. Standalone TUI appearances are unchanged. Desktop preference changes recolor existing terminal cells without input, restart, polling, or runtime IPC. The TUI pane follows desktop appearance; the console and Python panes retain their explicit always-dark override. The TUI's own appearance action emits only OSC 777;cadrumo;appearance;toggle, which the dedicated TUI pane may interpret as a frontend preference toggle; console/Python panes cannot invoke it. The payload carries no application state, and goes through ordinary PTY output, never diagnostics. No arbitrary commands or values are admitted by this presentation request.

ANSI roles retain background, surface, panel, foreground, muted text, primary, accent, status and border distinctions. Native ANSI rendering has fewer shade levels than the standalone RGB themes; verify actual widgets and contrast in both appearances. Reconsider this mechanism if future UI needs require additional color roles or a bidirectional presentation protocol.

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
- Logs from every Python process on the storage root that logs through `configure_logging` show in one place. That includes the runtime (`src/cadrumo_runtime/host/main.py:53`).

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

### Bottom-panel rail simplification amendment (2026-10-09)

Its startup-collapse and non-persistence clauses are superseded by the 2026-10-21 amendment; the paragraph below preserves the prior ruling.

Authorized by the user's request for one sidebar toggle instead of Console, Python and Logs buttons, retained notification counts, and a collapsed panel at application startup. The three rail buttons become one panel toggle using the existing panel-toggle action and shortcut. The existing log error count moves to this button, while the message notification count stays on Messages. Console, Python and Logs remain tabs in the panel, with their existing keyboard and palette actions. The active tab and panel size are remembered; open/closed state is local to the running window and is no longer restored or saved. Opening and collapsing preserve mounted terminal sessions within the same window. This refines frontend layout only and adds no host or runtime authority. Implementation: `native/desktop/frontend/src/App.tsx`, `src/shell/layout.ts`; browser assertions cover legacy saved-open startup, one toggle, both counts, tab retention and terminal reuse.

Amended 2026-10-16 under `2026-10-16-idle-churn-adr`: the shell no longer polls `sign-in-status`. It learns sign-in changes from one long-lived `cadrumo-runtime session watch` child, which re-reads only on a runtime cue, a pointer change or a status deadline. The sign-in view, language and agent hosts share that one observation. The shell process itself still holds no runtime connection, session, receipt or credential.

### Amendment 2026-10-18: component setup

Amended 2026-10-19 by the setup-experience amendment below; the paragraph that follows is the prior wording.

Accepted under the owner's advance authorization of 2026-10-18 recorded in `2026-10-18-dependency-provisioning-unified-setup-adr` (D10). The exceptions to "The shell holds no runtime connection and no runtime authority" gain one: while a profile is signed in, the host may read setup status and may start setup, answer its plan review, cancel it, and start Google sign-in, each through a closed, token-checked action of the held person bridge. The bridge pushes a cue when an observed setup operation changes, and the host re-reads it before pushing a typed snapshot to the shell. The frontend names items and choices only, never a command, path or host. Setup acts keep their registered-operation validation, and Google sign-in stays the runtime's authentication act. Noted 2026-10-18 under the owner's runtime-boundary ruling recorded in `2026-10-18-dependency-provisioning-unified-setup-adr`: the bridge carries these acts through its generic registered-operation relay and a generic authentication act, names no setup item, wording or definition, and the host keeps the window's own setup state; the host's commands stay closed. Noted again 2026-10-18 under the same ruling: the generic authentication act is removed, and Google sign-in is the product's registered `config.google.login` operation, which the host submits over the same relay and whose consent review it answers on the person's click. The shell still holds no session, receipt, credential, token or DEK, and stores no setup state beyond the per-launch dismissal of the first-run dialog. For setup only, this also amends "Shell settings are frontend preferences only. They never write product Settings or reach the backend": Settings gains a Components section whose buttons reach the backend through these actions, and the palette gains the setup actions of that record. Before this amendment, setup had no desktop surface and the exceptions named sign-in, profiles, manager start, named read-only views and language only.

### Amendment 2026-10-19: setup experience and the Google account

Basis: operator review 2026-10-19, recorded with its full commitments in `2026-10-18-dependency-provisioning-unified-setup-adr` (operator-review amendment). For this record:

- Setup covers software only: the browser and the local AI, which the window shows as one item. Google sign-in is not setup. The host's setup commands keep their shape; Google sign-in is carried by `desktop_google_sign_in` and sign-out by `desktop_google_sign_out`, both closed, token-checked commands over the same held person bridge's generic relay, submitting the product's `config.google.login` and `config.google.logout`. The host also reads the profile's stored sign-in through `config.google.status` and pushes it in the same snapshot, beside the setup rows and never among them. `desktop_setup_google_sign_in` is removed.
- Settings no longer embeds a Components section. While setup is unfinished or running it shows one top-level line that opens the setup flow, and nothing once setup is complete. Settings gains its own "Google account" row with the profile's signed-in state and one Sign in or Sign out button. Both are the only setup and account elements Settings carries; the exception to "Shell settings are frontend preferences only" covers exactly these two.
- The palette's setup group offers Set up components, Check components, Set up the browser, Set up the local AI, Retry setup and Cancel setup. The account group gains "Authenticate with Google". No setup action names Google.
- The setup dialog leads with one summary and one primary action, keeps per-component detail in a closed "Details" disclosure, and shows one overall progress bar while setup runs. Every row states its state once, by the product's sentence.
- Unchanged: the shell holds no session, receipt, credential, token or DEK, and stores no setup or account state beyond the per-launch dismissal of the first-run dialog. Where Google tokens are stored is not the shell's concern and is unchanged.

### Amendment 2026-10-21: saved views and single pane headings

Authorized by the user's design-polish request to remove repeated page titles, keep the TUI out of the default view, persist page view choices, and remember the selected log-level mode. The shell layout store is the single presentation preference owner. It restores the selected page, pane visibility and maximization, panel visibility/tab/size, calendar face and profile section/filter/disclosure choices, alongside existing appearance, arrangement and zoom preferences. The selected minimum log level overrides the host default until reset; resetting filters restores the host default. Fresh layouts open Profile and the agent where supported with the TUI closed. Existing saved TUI visibility remains an explicit saved arrangement.

This replaces the 2026-10-09 always-collapsed panel startup clause only; the single panel toggle, notifications and mounted-session retention still apply. The canonical pane header owns the visible page title and maximize control; page content supplies its own actions without repeating them. Profile navigation offers one section selector at each size. Search text, drafts, taxpayer values, log records, authentication and transient dialogs are not presentation settings and are not persisted here. Stored preferences are validated and tolerate unavailable storage. No runtime or host authority changes. Evidence: `native/desktop/frontend/src/shell/layout.ts`, `src/App.tsx`, `src/components/profile/UserProfilePage.tsx`, and `src/components/FilingCalendar.tsx`.

### Amendment 2026-10-21: cover embedded TUI startup until presentation is ready

Authorized by the user's request to hide the TUI startup sequence behind a loading view until ready. The existing terminal presentation seam also admits OSC 777;cadrumo;presentation;loading and OSC 777;cadrumo;presentation;ready, only in the dedicated TUI pane. These carry no profile, credential or authentication state and cannot admit a session. Process-start alone does not reveal the TUI. The canonical shared loading view covers receipt resumption, Textual app handoffs and initial workbench composition; the producer announces a rendered actionable screen. Automatic successful resumption does not announce its transient login form. A prompt needing input or a recoverable startup refusal is actionable and must be revealed. Terminal exit or failure must also remove the cover.

The frontend keeps parsing and acknowledging output while covered, including ConPTY cursor replies, and keeps terminal dimensions available. On Windows, OSC can precede buffered screen text: the frontend waits for a short output-quiescence interval and an xterm repaint before revealing readiness, restarting that wait for each output batch. This is a presentation settling guard, not a transport ordering guarantee or an authentication signal. No maximum startup timeout guesses readiness. Reconsider the settling guard if native traces show a repaint delayed beyond the guard; do not bypass runtime admission or add a second terminal launch.

Evidence: `src/cadrumo_runtime/host/frontend/tui/runtime_admission.py`, `src/cadrumo_runtime/host/frontend/tui/secret/runtime_login_form.py`, `src/cadrumo/entrypoints/tui/app.py`, `src/cadrumo/entrypoints/tui/components/quiet_app.py`, `native/desktop/frontend/src/components/TerminalPane.tsx`, and the real-PTY presentation test in `native/desktop/src-tauri/src/terminal/tests.rs`. The native Windows test observed an OSC marker emitted after screen text arriving before that text.

### Amendment 2026-10-22: cadrumo:// page links open the workspace page

Accepted by the user on 2026-10-22. A link `cadrumo://profiles/{id}/{page}` in an agent reply or a profile action raises the window (unminimize, show, focus), shows the TUI pane with keyboard focus, and, once the TUI is running, asks the held person session to present the page; the protocol, its closed page vocabulary and its admission rules are the 2026-10-22 amendment of `2026-08-11-tui-architecture-adr`. The link grammar is exact: a lowercase, non-nil profile UUID and one page among `home`, `ledger`, `withholding`, `declarations`, `aeat-sync`, `operations`, `installation`, `setup`, `reference`, `profile`, `aeat-auth`, with no query, fragment or further segment. The host, not the window, matches the link's profile against the active profile's identity, because the window knows the profile only by label.

No link is silent. A malformed link, a link for another profile, a signed-out window, a TUI that did not start or received nothing, and a refused request each show a toast; a link for another profile leaves the layout untouched. `cadrumo:` links never reach `open-external`. The modal AEAT setup terminal, its terminal target and its terminal kind are retired; AEAT setup opens the workspace's profile page, and the agent's check-again affordance follows a successful presentation.

Evidence: `native/desktop/frontend/src/components/agent/cadrumoLink.ts`, `native/desktop/frontend/src/App.tsx`, `native/desktop/src-tauri/src/shell/presentation.rs`, `native/desktop/src-tauri/src/agent/person.rs` (`presented_reply`), `native/desktop/src-tauri/src/shell/window_controls.rs`, and `native/desktop/frontend/tests/scenarios/agent-page-links.spec.ts`.

Amended 2026-10-22 under `2026-10-04-application-sign-in-adr` as amended that day: the sign-in host command signs the selected profile in through the window's person hold child instead of the canonical CLI login, which remains for a sign-in naming another profile.

### Amendment 2026-10-23: profile page actions, inline Censo and password change

Accepted by the user on 2026-10-23, who approved the profile page mockup with its change-password action and asked for it to be implemented. This refines the 2026-10-21 saved-views amendment for the profile page and adds one host exception.

- **Profile actions.** The profile page's actions are entries of the one action registry, so the palette, the page's actions button and its context menu offer the same list. Field actions (edit, copy, clear, about) follow the focused detail. The context menu and the actions button open through the shell's menu path, drawn by the operating system where the host can.
- **Saved profile view.** The layout store keeps the profile's show filter (all, unset, required, filled), grouping (section, status, none), sort (form order, missing first, alphabetical) and collapsed sections. It no longer keeps a selected section. The section selector is a section index while the page is full screen and wide enough, and a sections menu otherwise. A stored filter from before this amendment is read as the equivalent show filter.
- **Censo.** Synchronization is a band of the profile page, not a dialog. It uses the existing `profile_censo_*` commands unchanged. The incoming values of a review are shown on the details they would change, and the review is still answered as a whole, apply or reject, with its digest. The band shows no last-synchronized time, because no product read reports one.
- **Password change.** The host gains `profile_password_change`, a closed, token-checked command. It runs the canonical runtime CLI `config passphrase change --secrets-stdin` for the active profile. The current password, the new password and its confirmation travel in the command's raw body and the helper's standard input only. They are wiped on drop, and never appear in arguments, logs, diagnostics or the window's storage. The command line first proves the current password, then rotates the password without replacing the profile's data key. The window receives only a success or a refusal code. Nothing is retried, and an unconfirmed outcome is shown as unconfirmed. The shell still holds no session, receipt, credential, token or DEK.

Evidence: `native/desktop/frontend/src/components/profile/UserProfilePage.tsx`, `native/desktop/frontend/src/shell/layout.ts`, `native/desktop/frontend/src/App.tsx`, `native/desktop/src-tauri/src/shell/sign_in/password.rs`, and `native/desktop/frontend/tests/scenarios/user-profile.spec.ts`.

### Amendment 2026-10-24: the window's own person session

Accepted under the user's instruction of 2026-10-24 to implement native desktop sign-in, recorded with its commitments in `2026-10-04-application-sign-in-adr` (amendment of 2026-10-24). The sentences "signs the selected profile in through the window's person hold child" and "the shell process holds no session, receipt or credential" are kept as accepted history. The host now holds the person's runtime session for the selected profile on its own verified connection, and resumes a stored sign-in by reading the receipt proof the runtime minted. It holds it only while the window runs, never caches or forwards it to a terminal or TUI process, and still holds no DEK or password beyond the zeroized submission buffer. Every exception that named "the held person bridge" now names that session. The sign-in watch already ran on a native connection with no child since 2026-10-22, which also ends the `cadrumo-runtime session watch` child named in the 2026-10-16 note above.

### Amendment 2026-10-24: one navigation register for window and TUI links

Accepted by the user on 2026-10-24 ("all lgtm") after review of the link format and of where the register lives. It replaces the link grammar of the 2026-10-22 amendment; the TUI relay changes with it under the amendment of the same day in `2026-08-11-tui-architecture-adr`. `cadrumo://` is an internal register: only the window, its agent replies, its palette and the TUI use it. The scheme is not registered with the operating system, the single-instance activation carries no link, and a launch argument is never read as a link.

- **Grammar.** `cadrumo://view/{id}`, optionally followed by a query of the element's declared parameters and `prefer=gui` or `prefer=tui`, and nothing else. `{id}` has one to four segments, each matching `[a-z0-9]+(-[a-z0-9]+)*` and joined by `/`, for example `ledger/invoices`. A link is at most 512 characters, lowercase, with no fragment, credential, percent-encoding, repeated or undeclared query key. `view` is the navigation namespace. Other authorities on the scheme, such as the corpus citation keys, never resolve as a view. A link carries no profile: the window shows only the active profile, and a link grants nothing. The `cadrumo://profiles/{id}/{page}` form is no longer recognized, and stored replies that carry it show as malformed. The user accepted that break.
- **Register.** The vocabulary is declared once, as data, in `src/cadrumo_client/contracts/navigation.toml` with its validating loader `navigation.py`, shipped in the wheel. It is neutral: each element has an id, which is also its link path, a parent, one label locale key used by every palette, keywords, and the surfaces that implement it (`gui`, `tui`). Retired ids are append-only and never reused. The register does not declare how a surface implements an element. The window keeps its own id-to-layout table and the TUI its own id-to-destination table, and a coverage test on each side fails unless the table covers exactly the ids the register gives that surface. The desktop reads one generated projection, `navigation.json`, produced in the generator loop of `native/desktop/CMakeLists.txt` and served to the window as `virtual:desktop-navigation` and to the host through `build.rs`. The hand-written vocabularies in `cadrumoLink.ts`, `ipc/contract.ts` and `shell/presentation.rs` are removed.
- **Parameters.** Refined by the user on 2026-10-24: a link can point at a row, so the agent can report the link to an invoice or a movement it added. An element declares its own link parameters in the register, as a parameter name and a value kind, because which verbs make sense depends on the page; the set is to be revisited as pages ask for more. The first are `select` on `ledger/invoices` (an invoice) and on `ledger/movements` (a transaction), for example `cadrumo://view/ledger/movements?select={transaction id}`. A value is an opaque canonical record id of a declared kind with an exact grammar, never a natural key such as an invoice number, a tax id or an amount, because links reach agent replies and the clipboard. Parameters only show, select and focus; none edits, fills a form, submits or confirms. `prefer` is reserved for every element. Each key appears at most once, in any order, and the formatter writes declared parameters in sorted order and `prefer` last. A surface honours a link only if it implements the element and every parameter given; otherwise resolution continues in the stated order and drops a parameter only with a notice that says so. A selected row is revealed, scrolled into view, selected and focused. A row hidden by the person's own filter, grouping or collapsed section is announced with an action to show it, and the saved view is not changed silently. A record that is not found leaves the page open with a notice that does not say whether it exists anywhere else. MCP results that name exactly one record of a selectable kind carry its link, formatted by the same client function.
- **Resolution.** The preferred surface, which is the window unless the link asks for the TUI, opens the element. Otherwise the other surface opens it with a notice saying where it opened. Otherwise the nearest ancestor opens in the preferred surface, then in the other, with a notice. Otherwise the link is refused with a toast. No link is silent.
- **Verbs.** A link shows and focuses its element and is idempotent. It never toggles anything away, edits, submits, confirms or answers a prompt. The palette may also toggle panes and panels.
- **Search.** The palette's view actions derive from the register, so a label, chord or id is declared once. The palette matches the localized label, keywords and id. A pasted `cadrumo:` link is one entry that opens it, or a refusal that says why. A copy-link action copies the current view's link.
- **TUI pages.** The host command that presents a TUI page takes a register id whose surfaces include `tui`, checks it against the generated projection, and asks the held person session for the active profile. Without a sign-in it reports `signed_out`. The other-profile outcome is retired with the profile segment.
- **Unsaved and in-flight work.** Every navigation from a link, the palette, the rail, a page, sign-out, a profile switch or the window's close passes one guard register. The window works out which mounted owners the navigation would unmount: leaving a page unmounts that page, while showing a pane, panel or TUI page unmounts nothing. Each guard reports one state:
  - `clean` lets the navigation through;
  - `dirty` (staged or drafted values) asks once whether to discard or stay;
  - `busy` (an effect in flight whose outcome the owner must show) refuses with a toast and offers no override, because unmounting would lose a possibly `UNKNOWN` outcome;
  - `modal` (an open dialog or credential form anywhere in the window) stands down every navigation except the window's close with a toast and keeps the form, as the TUI does.

  A navigation that unmounts nothing is never asked about. One navigation waits for an answer at a time; another request in that time shows a toast and does nothing. The window's close keeps its 2026-10-24 titlebar behavior, which the guard can never turn against the person: an open dialog never holds a close, a dirty or busy owner is asked about rather than refused, a close that arrives while a question is waiting is left unanswered, and a second close always closes. Reconciled 2026-10-24 after the plan-close review found the first wording let a dialog hold the close; before that this sentence read: "The window's close keeps its 2026-10-24 titlebar behavior: a busy owner is asked about rather than refused, and a second close still closes."
- **Focus.** After a navigation applies, the element's focus target takes keyboard focus when the element signals that it is mounted, not after a delay. A TUI page still shows the TUI pane with focus first.

Rejected: a register outside the repository shared with cadrumo-agent (two release trains for vocabulary only this repository implements; the agent reads the register as Cadrumo's MCP service publishes it instead); a repo-level declaration such as `native/application-environment.toml` (the pip TUI and the relay read the register at runtime without a native package, so it would need a generated module checked into `src`); a typed Python module as owner (it puts the shell's page state under a Python package and cannot type the TUI targets across the client boundary); registering each surface's internal targets in the register (a lower component would define the application's page state); `<window>` or the surface as the first path segment (the same element would have two identities); a profile segment (it only produced a refusal and grants nothing); OS protocol registration and single-instance forwarding; a URL router; and keeping hidden pages mounted to avoid prompts.

Evidence: the register `src/cadrumo_client/contracts/navigation.toml` with its loader `navigation.py`, the shared cases `src/cadrumo_client/contracts/tests/navigation_vectors.json` and the shipped-id baseline `navigation_shipped_views.json`; the projection `dev/packaging/native/desktop_navigation.py` in `native/desktop/CMakeLists.txt`; the host command `native/desktop/src-tauri/src/shell/presentation.rs` and the reply checks in `src/agent/person.rs` and `src/agent/person/native.rs`; the window core `native/desktop/frontend/src/shell/navigation/` (`links.ts`, `resolve.ts`, `windowViews.ts`, `guards.ts`, `focus.ts`, `reveal.ts`, `useNavigator.ts`), `components/NavigationPrompt.tsx`, `components/ledger/RowReveal.tsx`, the modal layer of `components/ui` dialogs, and the palette in `shell/actions.ts` and `App.tsx`; and the scenarios `navigation-register.spec.ts`, `agent-page-links.spec.ts`, `navigation-guards.spec.ts`, `window-close.spec.ts` and `palette.spec.ts` under `native/desktop/frontend/tests/scenarios/`. The plan-close review and its fixes are in `2026-10-24-desktop-navigation-register-audit`.

### Amendment 2026-10-24: component setup runs in the window's own engine

Basis: the owner's approval of 2026-10-24, "all approved, implemnet", answering the presented `2026-10-24-rust-component-provisioning-adr` and its two plans.

The host's setup commands call the Rust component engine of `2026-10-24-rust-component-provisioning-adr` in process instead of relaying the `dependencies.*` operations over the person bridge. The window contract (`desktop_setup_*` commands, `DesktopSetup` and the refusal codes) is unchanged, and so are the Settings advisory, the setup flow and the blocked-feature prompts of the 2026-10-19 amendment.
