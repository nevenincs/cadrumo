---
tags:
  - '#research'
  - '#desktop-shell-capabilities'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:75b04b347ff8617600443f19d4b42229bdca7a027083b3cc5c17d2cc51f66cf6'
related:
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
---

# `desktop-shell-capabilities` research: `what the desktop shell can reach today for profiles, TUI destinations, rail data and exports`

On 2026-10-06 the user asked for the desktop shell to handle a missing profile, to offer profile creation, to gain rail buttons for the tax agency's site, messages, the profile's Drive folder, sync and a filing calendar, to open the TUI at a chosen page, to list TUI pages in the palette, and to confirm that filing exports land somewhere safe. This record establishes what each of those can reach today. The picture: one of them needs nothing new, the rest need either a host command the shell does not have or a ruling the accepted decisions do not contain, and the export has no default location at all.

## Findings

### The shell reaches the product only by spawning the command line for sign-in

The host's commands are sign-in status, sign-in, sign-out, the environment, terminals, diagnostics, logs, external links, the clipboard and context menus (`native/desktop/frontend/src/ipc/contract.ts:492`). Only the sign-in family touches the product, and it does so by running the `aeat` binary as a short child process with fixed arguments and bounded output (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:61`, `native/desktop/src-tauri/src/shell/sign_in/process.rs:50`). There is no general bridge to a command and no connection to the runtime. `2026-10-04-desktop-shell-adr` makes that a ruling: the shell holds no runtime connection and no runtime authority, with three named exceptions, all about sign-in (`.vault/adr/2026-10-04-desktop-shell-adr.md:83`).

### A missing profile and an unchosen one are reported identically

`config sign-in-status` reads the active-profile pointer and, when no profile is selected, reports absent presence without asking the runtime (`src/cadrumo/entrypoints/cli/config/custody.py:302`). The shell therefore receives no active profile and absent presence both when no profile was ever created and when profiles exist but none is chosen. The command line already tells the two apart elsewhere, from the profile manifests, without unlocking anything (`src/cadrumo/entrypoints/cli/common.py:1014`); the status result does not carry it.

### Profile creation is scriptable, and first run is ruled to the TUI

`config profile create` registers a profile from a label and a passphrase read from a pipe or a no-echo prompt, never from arguments (`src/cadrumo/entrypoints/cli/config/scripted_registration.py:70`). It runs in process and needs no runtime (`src/cadrumo/application/user_profile/registration.py:149`). The profile is born incomplete; its tax facts are collected afterwards by the TUI's setup wizard. `2026-10-04-application-sign-in-adr` rules that the desktop sign-in view covers the active profile only and that first run, other profiles, recovery and a locked profile hand over to the TUI (`.vault/adr/2026-10-04-application-sign-in-adr.md:158`). Three options follow: keep the handover; add registration of label and passphrase to the shell through a host command shaped like sign-in, then sign in, then hand the wizard to the TUI; or bring the wizard into the shell. The second needs a host command, a profile-exists signal in the status, and a ruling that widens the shell's exceptions. The third would move taxpayer fact collection into the shell and was not investigated.

### The TUI owns its navigation, and names a peer as the one exception

The host starts the TUI with a fixed argument list and no per-open parameter (`native/desktop/src-tauri/src/terminal/mod.rs:92`). The TUI's entry point refuses every argument but its self-test flag (`src/cadrumo/entrypoints/tui/launcher.py:38`). Inside, a closed catalogue names six destinations (`src/cadrumo/entrypoints/tui/navigation.py:30`) and one function applies a target, falling back to Home when it is refused (`src/cadrumo/entrypoints/tui/app_navigation.py:26`). A filing or calendar entry resolves to the declarations destination plus a focus token (`src/cadrumo/entrypoints/tui/app_navigation.py:65`). The amendment of 2026-09-08 to `2026-08-11-tui-architecture-adr` forbids a launcher from selecting a destination and adds that any destination protocol is internal to the TUI unless a separately identified peer that is not the command line needs it (`.vault/adr/2026-08-11-tui-architecture-adr.md:1519`). The desktop shell is such a peer, so a protocol for it is open to a decision rather than closed. The only channel into a running TUI today is keystrokes, which the TUI's own sign-in and modals intercept. Options: a destination argument at launch, which the amendment retired; typed keystrokes, which are unreliable; or a request the TUI itself reads after its own sign-in and applies through its existing function. The evidence favours the last. How the request travels from the shell to the TUI was not settled: a profile-bound record written through a registered operation is one candidate.

### Notifications and the calendar have command-line reads; sync counts and the Drive folder do not

Captured notifications are read through registered, no-effect operations surfaced as `app live notifications list`, `show` and `latest` (`src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py:102`); an unread count is a filter on a row field, not a field of its own (`src/cadrumo/application/live/notifications.py:113`). The filing calendar is `app overview calendar` (`src/cadrumo/entrypoints/cli/_overview_command_specs.py:104`), local only by `2026-06-04-calendar-live-filing-integration-adr`. Both require an exact-profile client under the signed-in session, which only the command-line process holds. The sync workspace projection distinguishes never captured, unknown and captured (`src/cadrumo/application/aeat_sync/workspace_reader.py:601`) but is internal to the TUI: no command exposes it, and `2026-08-08-sync-control-surface-adr` records the preview of what a sync would change as not implemented. No pair of counts for available and already synced exists anywhere. For Drive, `2026-10-04-google-app-identity-adr` commits to app-created files only and to no command accepting a folder reference; no folder address is stored, and that record names opening a folder the user owns as needing a new decision.

### The tax agency's site needs nothing new

The address is a product constant (`src/cadrumo/core/external_constants.toml:13`) and the host's external-link command admits any well-formed https address (`native/desktop/src-tauri/src/shell/external.rs:29`).

### A filing export has no default location

The export command refuses a missing, blank or current-directory destination (`src/cadrumo/entrypoints/cli/_modelo_export_cli.py:105`) and the TUI's export refuses a blank one (`src/cadrumo/entrypoints/tui/modelo/workbench/export.py:263`). The write is staged beside the target under an unguessable name, synced, and published without replacing an existing file unless asked (`src/cadrumo/application/modelo/export_sink.py:53`, `src/cadrumo/core/atomic_write.py:550`); the staged file is created owner-only on POSIX. Gaps: on Windows the file takes the chosen folder's access list, because hardening is applied only to directories the product creates (`src/cadrumo/core/atomic_write.py:374`); a relative destination is resolved against the issuing process's working directory in both the command line (`src/cadrumo/entrypoints/cli/_modelo_export_cli.py:132`) and the TUI (`src/cadrumo/entrypoints/tui/modelo/lifecycle.py:255`), which differs between a terminal and the desktop application; the plaintext file's lifetime is left to the operator; and no test asserts the file's mode. Not determined: which process performs the write, and its working directory, when the request is served by the runtime's worker.

## Sources

- `native/desktop/frontend/src/ipc/contract.ts:492`
- `native/desktop/src-tauri/src/shell/sign_in/mod.rs:61`
- `native/desktop/src-tauri/src/shell/sign_in/process.rs:50`
- `native/desktop/src-tauri/src/shell/external.rs:29`
- `native/desktop/src-tauri/src/terminal/mod.rs:92`
- `src/cadrumo/entrypoints/cli/config/custody.py:302`
- `src/cadrumo/entrypoints/cli/common.py:1014`
- `src/cadrumo/entrypoints/cli/config/scripted_registration.py:70`
- `src/cadrumo/application/user_profile/registration.py:149`
- `src/cadrumo/entrypoints/tui/launcher.py:38`
- `src/cadrumo/entrypoints/tui/navigation.py:30`
- `src/cadrumo/entrypoints/tui/app_navigation.py:26`
- `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py:102`
- `src/cadrumo/application/live/notifications.py:113`
- `src/cadrumo/entrypoints/cli/_overview_command_specs.py:104`
- `src/cadrumo/application/aeat_sync/workspace_reader.py:601`
- `src/cadrumo/core/external_constants.toml:13`
- `src/cadrumo/entrypoints/cli/_modelo_export_cli.py:105`
- `src/cadrumo/entrypoints/tui/modelo/workbench/export.py:263`
- `src/cadrumo/entrypoints/tui/modelo/lifecycle.py:255`
- `src/cadrumo/application/modelo/export_sink.py:53`
- `src/cadrumo/core/atomic_write.py:374`
- `.vault/adr/2026-10-04-desktop-shell-adr.md:83`
- `.vault/adr/2026-10-04-application-sign-in-adr.md:158`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:1519`

The locators under `src/cadrumo/application/live`, `aeat_sync`, `modelo/export_sink.py`, `tui/modelo` and `common.py` come from delegated reading and were not opened again when this record was written; the others were.
