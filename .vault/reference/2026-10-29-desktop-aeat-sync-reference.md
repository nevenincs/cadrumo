---
tags:
  - '#reference'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:a927543665d2644556ef02af83e2a2edcda167f39bb0a2b283ac95ba27c6ea93'
related: []
---
# `desktop-aeat-sync` reference: `AEAT sync page grounding: reads, captures, host relay and setup`

## Summary

Code facts that ground the AEAT sync page decision, verified on 2026-10-29 in the `feature/tui` worktree.

## Navigation and existing projection

- `aeat-sync` is a `gui` register element (`src/cadrumo_client/contracts/navigation.toml:107`) with no entry in `native/desktop/frontend/src/shell/navigation/windowViews.ts`; `src/cadrumo/application/operations/operation_pages.py:15` maps `live.` operations to it.
- `read_local_aeat_sync_workspace_projection` (`src/cadrumo/application/aeat_sync/workspace_reader.py:627`) is the only public reader and is called only from `src/cadrumo/application/workbench_generation_reader.py:925`, inside `workbench.generation`. Its zones are census, filed declarations, notifications, evidence comparison and reconciliation (`src/cadrumo/application/aeat_sync/workspace.py:79`); availability values are available, locked, stale, never captured and unavailable (`workspace.py:102`).
- Census capture time comes from `read_latest_censal_observation` (`src/cadrumo/application/user_profile/censal_readback.py:23`), which no registered read exposes; `CensalObservation.captured_at` is at `src/cadrumo/application/user_profile/censal_observation.py:106`.
- The typed sync-run record exists for the filed sweep only (`src/cadrumo/application/storage/sync_runs/records.py`, written at `src/cadrumo/application/live/filed_data_capture.py:705`); no read operation returns it.

## Operations

- Every live capture declares cancellation `unsupported` and no interaction kinds; `user-profile.censo-review` (review interaction) and `live.sede.view` are cooperative (`src/cadrumo/_data/operations/contract_manifest.json`).
- Census is captured inside `user-profile.censo-review` (`src/cadrumo/application/user_profile/censal_operation.py:505`); `user-profile.censo-prepare` does not contact AEAT.
- `live.filed-capture.bulk` takes `output_root`, `year_from`, `year_to`, optional `modelos`, `limit`, `dry_run` and returns `failed_count`, `pair_outcomes`, `failures`, `sync_run_ref` (`src/cadrumo/application/live/filed_bulk_capture_operation.py:49`, `:88`).
- `live.filed-history.pull` bundles IVA wallet and notification stages (`src/cadrumo/application/live/filed_history_events.py:18`) and emits typed progress events.
- `output_root` roots report paths only; records go to the encrypted store (`src/cadrumo/application/live/filed_history_operation.py:115`). The CLI defaults it from settings (`src/cadrumo/entrypoints/cli/app_live_commands.py:312`; `src/cadrumo/core/config.py:792`).
- `live.verify.nif-iva` and `live.verify.tgvi` require `nif` (`src/cadrumo/application/live/verify_capture_operation.py:74`). `live.iva-wallet.history-capture` requires `output_root`, `year_from`, `year_to` (`src/cadrumo/application/live/iva_wallet_history_capture_operation.py:47`). `live.notifications.capture` takes the profile only. No Borrador 100 capture exists; `live.borrador.100.import` reads a local PDF.

## Desktop host

- Census host session: `ProfileHost.censo` (`native/desktop/src-tauri/src/shell/user_profile.rs:54`); commands `profile_censo_readiness`, `_start`, `_status`, `_answer`, `_observe`, `_unobserve` (`native/desktop/src-tauri/src/shell/user_profile/censo.rs:401`); repeat start reattaches (`censo.rs:284`); cancel goes through `operation_cancel` (`censo.rs:367`); observation is a `Channel<()>` cue (`censo.rs:423`).
- Relay: `submit` (`native/desktop/src-tauri/src/shell/relay.rs:123`), `accepted` maps a lost mutation reply to unknown (`:223`), `observe` (`:244`) reads only the projection with `after_cursor` 0, `follow` (`:273`), `result` (`:296`), `SETTLE_LIMIT` 90 s (`:13`).
- Setup engine: `desktop_setup_read`, `desktop_setup_start(item)` with items `browser` and `local_ai`, `desktop_setup_observe` (`native/desktop/src-tauri/src/shell/setup/mod.rs:712`, `:735`, `:804`; `setup/wire.rs:512`). Census refusals for a missing browser already route to setup (`native/desktop/frontend/src/App.tsx:947`).
- Sede view: `sede_view_open` takes only a size (`native/desktop/src-tauri/src/shell/sede_view.rs:1643`); it cannot open at an address.
- AEAT access: `profile_aeat_certificate_pick`, `profile_aeat_credential_save` (`native/desktop/src-tauri/src/shell/user_profile.rs:653`, `:665`); no host command submits `auth.session.acquire`.
- The census review band is `native/desktop/frontend/src/components/profile/ProfileSync.tsx`, used by `UserProfilePage.tsx`; no palette or Modelo page entry to it was found.
