---
tags:
  - '#plan'
  - '#desktop-navigation-register'
date: '2026-10-24'
tier: L1
related:
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:59b7360dfe38a39d587aedb9c23ba5fd66861884ef403309c7806dc85d346a9c'
---

<!-- RETIRED: S01, S02, S03, S04, S05 -->

# `desktop-navigation-register` plan

One register of navigable window and TUI elements behind `cadrumo://` links and the palette, with a guard register that protects unsaved and in-flight work.

## Description

Approved 2026-10-24. Basis: the user's instruction of 2026-10-24 to extend `cadrumo://` navigation from the TUI to the React window, with registered, searchable elements, palette integration, focus of the requested interface and handling of work a navigation would destroy; the user's same-day rulings that `cadrumo://` is internal, that links are `cadrumo://view/{id}` with a surface preference and no profile, that old links may break, that the register is neutral data in the client contracts and is published through MCP; and the user's "all lgtm" on the amendments.

Decision coverage: the 2026-10-24 amendments of `2026-10-04-desktop-shell-adr` (grammar, register, resolution, verbs, search, host TUI command, guards, focus) and `2026-08-11-tui-architecture-adr` (relay id, TUI mapping, link producers, MCP publication) govern every Step. No OS registration, launch argument or single-instance work is in scope. The cadrumo-agent project's use of the published register belongs to the cadrumo-agent session, which `S08` briefs.

The worktree is shared with sessions editing `App.tsx`, `contract.ts`, `tauriHost.ts`, the ledger components and TUI declarations modules: each Step re-reads a file before patching, keeps its hunks minimal, and commits only its own hunks through a private index built from HEAD, then resyncs those paths in the shared index.

## Steps

- [x] `S06` - Author the neutral navigation register and its validating loader with the initial element set (the TUI pages, profile/aeat-access, the window pages and ledger sections, panes and panel tabs), the link format and parse functions for cadrumo://view/{id} with prefer, ship the TOML in the wheel, add its label keys through the locale workflow in every locale, and test grammar, parent closure, append-only retired ids and label coverage; `src/cadrumo_client/contracts/navigation.toml, src/cadrumo_client/contracts/navigation.py, src/cadrumo_client/contracts/tests/, pyproject.toml, dev/locales/`.
- [x] `S07` - Move every Python consumer to the register in one change: runtime relay admission by register tui ids, the TUI id-to-destination table with its exact-coverage test and profile/aeat-access, operation_pages mapping to register ids, the AEAT setup handoff and the MCP page url through the link formatter; delete PresentationDestination and destination_link; `src/cadrumo_client/contracts/presentation.py, src/cadrumo_client/contracts/session_events.py, src/cadrumo_runtime/host/, src/cadrumo/entrypoints/tui/presentation.py, src/cadrumo/application/operations/operation_pages.py, src/cadrumo/application/auth/setup_handoff.py, src/cadrumo_mcp/mcp/admitted_operations.py, their tests`.
- [x] `S08` - Publish the register through the MCP service as deterministic searchable data with ids, parents, labels, keywords and surfaces, with protocol tests, and brief the cadrumo-agent session on the tool and the link grammar; `src/cadrumo_mcp/`.
- [x] `S09` - Project the register to navigation.json in the desktop generator loop, serve it as virtual:desktop-navigation and to the host through build.rs, replace the host TUI presentation command with one taking a register id for the active profile, and delete the hand-written vocabularies; `dev/packaging/native/ or dev/locales/ generator, native/desktop/CMakeLists.txt, native/desktop/frontend/vite.config.ts, native/desktop/src-tauri/build.rs, native/desktop/src-tauri/src/shell/presentation.rs, native/desktop/src-tauri/src/agent/person.rs, native/desktop/frontend/src/ipc/contract.ts, native/desktop/frontend/src/shell/host.ts, native/desktop/frontend/src/shell/tauriHost.ts, native/desktop/frontend/src/dev/scenarioHost.ts`.
- [x] `S10` - Build the window navigation core and route every navigation through it: link parse and format, the id-to-layout table with its exact-coverage test, resolution with fallback notices, the guard register with clean, dirty, busy and modal, the navigator with mount-signalled focus, the ledger guard ported, links, rail, sign-out, switch and close guarded, and the old cadrumoLink removed; `native/desktop/frontend/src/shell/navigation/, native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/agent/, native/desktop/frontend/src/components/ledger/editing/LedgerEditing.tsx, dev/locales/, native/desktop/frontend/tests/scenarios/agent-page-links.spec.ts`.
- [x] `S11` - Register the pages' own guards and focus targets: profile field draft, Censo review and password dialog, ledger invoice editor, draft review and ratios, open dialogs as modal, with scenarios for dirty, busy, modal and no-prompt pane navigation; `native/desktop/frontend/src/components/profile/, native/desktop/frontend/src/components/ledger/, native/desktop/frontend/src/components/ui/, native/desktop/frontend/tests/scenarios/`.
- [x] `S12` - Derive the palette's view actions from the register keeping existing ids and chords, add label, keyword and id search, a pasted-link entry and a copy-link action, with palette scenarios; `native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/CommandPalette.tsx, native/desktop/frontend/src/shell/actions.ts, dev/locales/, native/desktop/frontend/tests/scenarios/keyboard.spec.ts`.
- [ ] `S13` - Record the landed evidence in both 2026-10-24 amendments and run the integrated review; `.vault/adr/2026-10-04-desktop-shell-adr.md, .vault/adr/2026-08-11-tui-architecture-adr.md`.

## Parallelization

`S06` lands first: every other Step consumes the register. Then two lanes run in parallel with disjoint write ownership. The Python lane is `S07` and then `S08`, under `src/`. The desktop lane is `S09` and then `S10`, under `native/` and the generator. `S09` reads the TOML only through the generator. After `S10` is committed, `S11` (page components) and `S12` (palette and its block in `App.tsx`) run in parallel. Locale batches from any lane are serialized through one owner at a time. `S13` runs last.

## Verification

- The register loader refuses a bad id, an unknown parent, a cycle, a reused retired id, a missing label key and an element without a surface.
- The link parser accepts `cadrumo://view/{id}` with and without `?prefer=gui|tui`. It refuses the old profile form, other authorities, uppercase, fragments, other or repeated query keys, percent-encoding, more than four segments and input over 512 characters.
- The TUI table and the window table each cover exactly their surface's register ids, and the tests fail on a missing or extra id.
- The runtime relays a register `tui` id and refuses others. A TUI link opens the TUI page with focus. A GUI link opens and focuses the window element. A GUI-only element asked for with `prefer=tui` opens in the window with a notice. An element no surface implements falls back to its nearest ancestor with a notice.
- With staged ledger work, a link to another page asks and keeps the work on stay. With an effect in flight it refuses with a toast. With a dialog open it stands down. Showing a pane asks nothing.
- The palette finds elements by localized label, keywords and id, opens a pasted link, and copies the current view's link. Existing chords and action ids still work.
- MCP returns the register as data, and its page URLs use `cadrumo://view/{id}`.
- Owning recipes pass for the touched scopes: the pytest paths through the justfile lanes, `npm run check`, the Playwright `scenarios` project for touched specs, the desktop crate tests for `shell::presentation`, the locale parity tests, import boundaries, style and types.
- The plan is complete when every Step is closed and the integrated review passes.
