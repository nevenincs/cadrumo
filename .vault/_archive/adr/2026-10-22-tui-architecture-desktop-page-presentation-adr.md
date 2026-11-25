---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:3991976940c3e831f592c235cd9ec9679b2cbf739f8c8f6a698646f694178806'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-06-desktop-shell-capabilities-research]]"
---

# `tui-architecture` adr: `the desktop asks the running TUI to show a page` | (**status:** `proposed`)

## Problem Statement

A `cadrumo://` link in an agent reply did nothing in the desktop. The window matched the link's profile UUID against the signed-in profile's label, which never matched; every other `cadrumo://` link was dropped without a word. The one link Cadrumo produces, `cadrumo://profiles/{id}/aeat-auth` from the MCP auth handoff (`src/cadrumo/application/auth/setup_handoff.py:41`), opened a second TUI process in a modal dialog instead of the workspace the person already has open. The desktop had no way to ask its running TUI for a page: `2026-10-06-desktop-shell-capabilities-research` found keystrokes the only channel and left the transport undecided, and the 2026-09-08 amendment to `2026-08-11-tui-architecture-adr` keeps any destination protocol TUI-internal unless a non-CLI peer needs one. The desktop is that peer.

## Considerations

- The TUI already resolves and admits a closed destination catalogue through one function (`src/cadrumo/entrypoints/tui/navigation.py`, `src/cadrumo/entrypoints/tui/app_navigation.py`).
- The runtime already pushes nonsecret, exact-session cues to frontend connections, and the TUI already subscribes to some (`src/cadrumo_client/contracts/session_events.py`).
- The desktop's runtime connection is the held person session (`src/cadrumo_runtime/host/session_hold.py`); the TUI it hosts holds its own connection on the same profile.
- `portable-pty` cannot hand an extra inherited handle to the TUI child, and Windows ConPTY does not pass unknown input OSC sequences through to Textual's parser.
- The command line never selects a TUI destination (the 2026-09-08 amendment).

## Considered options

- **A runtime cue from the desktop's held session to the person's TUI connections (chosen).** It reuses verified connections and the existing event stream on both ends; the runtime relays a closed token and interprets no route.
- **A desktop-owned pipe or socket named to the TUI child at spawn.** Rejected: new native IPC on every platform, a new environment variable, and peer verification the runtime already performs.
- **A private escape sequence written into the TUI's terminal input.** Rejected: Textual's input parser has no OSC support and ConPTY may drop the sequence; anything typed or pasted could imitate it.
- **Relaunching the TUI with a page argument.** Rejected: it discards the person's open work, and the 2026-09-08 amendment retired launch-time destinations.

## Constraints

- The page vocabulary is closed and names pages only: `home`, `ledger`, `withholding`, `declarations`, `aeat_sync`, `operations`, `installation`, `setup`, `reference`, `profile`, `aeat_auth`. It carries no profile facts, query, or credential.
- Only a desktop-frontend person connection may ask; a CLI or TUI frontend is refused with `frontend_denied`, and a non-person peer with `person_act_required`. The asking session is checked as a status read is.
- The runtime sends the request only to TUI connections on the same profile that hold a session under the same native login, and reports how many it reached. Delivery grants nothing.
- The TUI admits a requested page exactly as it admits a palette choice. Over a credential or modal form it stands down with a visible notice rather than discarding the form.
- A link the desktop cannot act on is never silent and never reaches the system browser.
- This amends the 2026-09-08 amendment of `2026-08-11-tui-architecture-adr` (the desktop is the named non-CLI peer) and the external-link rule of `2026-10-04-desktop-shell-adr` (`cadrumo://` page links are handled inside the window). The separate AEAT setup TUI (`--aeat-auth-profile`) is retired; the TUI's invocation grammar stays the bare and self-test forms.

## Implementation

We will carry a page request from the desktop to its running TUI through the runtime. A link `cadrumo://profiles/{profile}/{page}` raises the desktop window, shows the TUI pane with keyboard focus, and, once the TUI runs, asks the held person session for `present_destination`. The runtime publishes a `presentation_requested` cue to the person's signed-in TUI connections on that profile; the TUI maps the page to its navigation target and opens it. `aeat-auth` opens the profile page with its AEAT access editor.

The contract lives in `src/cadrumo_client/contracts/presentation.py` and `src/cadrumo_client/contracts/session_events.py`; the runtime handler is `_present` in `src/cadrumo_runtime/host/profile_connection_sessions.py`; the TUI side is `src/cadrumo/entrypoints/tui/presentation.py`; the desktop side is `native/desktop/src-tauri/src/shell/presentation.rs` and `native/desktop/frontend/src/components/agent/cadrumoLink.ts`.

## Rationale

The chosen option is the only one that targets the TUI the person is looking at without new native IPC or an input channel others could imitate, and it keeps route admission where the TUI architecture places it. The runtime's role stays protocol-neutral: it checks the asker's session and relays a closed token.

## Consequences

- Agent replies and the desktop's own profile actions can open any workspace page, and a failure says why.
- A standalone TUI the same person runs on the same profile also receives the request; that is the person's own workspace and the request grants nothing.
- A TUI still on its sign-in screen receives nothing, and the desktop tells the person to wait or sign in.
- Adding a page means extending the closed vocabulary in the client contract, the TUI mapping, and the desktop link grammar together.
