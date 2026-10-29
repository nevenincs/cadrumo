---
tags:
  - '#adr'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:0c96b47ed3610089342ffdc119ce4b59b48817483dd46c1cef4635441594ae34'
related:
  - "[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-10-27-sede-browser-adr]]"
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-08-08-synced-history-consumption-adr]]"
  - "[[2026-10-03-aeat-live-write-guard-adr]]"
  - "[[2026-06-04-live-auth-decomposition-adr]]"
  - '[[2026-10-29-desktop-aeat-sync-reference]]'
---
# `desktop-aeat-sync` adr: `AEAT sync page: backend area status read and host-run area queue` | (**status:** `accepted`)

Accepted by the owner on 2026-10-29 ("approved"), after ruling the open questions recorded under Owner rulings.

## Problem Statement

The register element `aeat-sync` (`src/cadrumo_client/contracts/navigation.toml:107`) has no window view in `native/desktop/frontend/src/shell/navigation/windowViews.ts`, so it resolves as not implemented. The person needs one page that shows, for census, filed declarations, notifications, VAT balance carried forward (IVA wallet), Borrador 100 and identity checks, whether each was never brought, is up to date as of a date, may be out of date, or could not be checked; and a flow that checks the secure browser, signs in to AEAT, brings the chosen areas with live progress and stop, and shows distinct outcomes and results. Reads only; nothing is submitted.

No product read answers the overview cheaply. `workbench.generation` carries the AEAT sync projection (`src/cadrumo/application/aeat_sync/workspace_reader.py:627`, called only from `src/cadrumo/application/workbench_generation_reader.py:925`) but is human-only, regenerates the whole workbench and leaves notifications never captured, census always available and staleness uncomputed. The census capture time has no public read outside it (`src/cadrumo/application/user_profile/censal_readback.py:23`). `live.verify.latest` needs a tax number the window must not hold. The host may submit only named, fixed reads (`2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr`) and the window holds no domain data or logic (`2026-10-04-desktop-shell-adr`, amendment 2026-10-27).

## Considerations

- Staleness ("may be out of date") is a judgement about tax-relevant data, so it belongs to the backend and is served to every frontend (`2026-10-04-desktop-shell-adr`, amendment 2026-10-27).
- Never captured, stale, unknown and empty stay distinct; an unknown is never drawn as zero (`2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr`).
- Every live capture declares cancellation `unsupported` and no interaction kinds in `src/cadrumo/_data/operations/contract_manifest.json`; only `user-profile.censo-review` and `live.sede.view` are cooperative.
- The relay has no progress stream; the runtime observation carries an event cursor the host does not read yet (`native/desktop/src-tauri/src/shell/relay.rs:244`); filed captures emit typed progress events (`src/cadrumo/application/live/filed_history_events.py`).
- Capture records go to the encrypted profile store; `output_root` only roots report paths and the CLI defaults it from settings (`src/cadrumo/entrypoints/cli/app_live_commands.py:312`, `src/cadrumo/application/live/filed_history_operation.py:115`).
- The desktop reads component rows before a feature that needs one (`2026-10-18-dependency-provisioning-unified-setup-adr` D8, `2026-10-24-rust-component-provisioning-adr` constraint 13).
- The Sede view shares session custody and cannot open at an address (`2026-10-27-sede-browser-adr`).
- Pulled facts are evidence, not calculation inputs (`2026-08-08-synced-history-consumption-adr`); Cadrumo never submits (`2026-10-03-aeat-live-write-guard-adr`).

## Considered options

- **Reuse `workbench.generation`.** Rejected: whole-workbench cost on every page open, human-only, and it still lacks notifications, IVA wallet, Borrador, identity checks and staleness.
- **Compose existing latest reads in the host and judge staleness there.** Rejected: census time has no read, identity checks need the tax number, and the staleness rule and area grouping would be domain logic outside the backend, unavailable to the CLI and TUI.
- **One new registered read, `live.sync.status`, built on the existing AEAT sync reader.** Kept: one cheap, no-network, no-effect projection that every frontend can use and that `workbench.generation` keeps consuming.
- **One composite capture operation for the whole run.** Rejected: a new costly backend workflow duplicating per-area operations; a host queue over existing operations gives stop points and resume.
- **Run `live.filed-history.pull` for "everything".** Rejected for the window: it bundles IVA wallet and notification stages into one uncancellable run with no year-level stop point; the window uses the discover leaf plus per-year bulk capture.

## Constraints

- The window shows only served values remapped to wording. No operation id, snapshot id, path, tax number of a third party or error code reaches it; codes stay in the host, which maps them to closed outcome and reason values.
- Every operation used is a read of AEAT or a local read. No submission path is added.
- The host submits only a closed list of definition ids, a Rust constant checked by test against the contract manifest; adding an id amends this record.
- Outcome `unknown` is never retried automatically. A failed item is retried only by an explicit person action; an unknown item only after the person is told it may already have been brought.
- Provisioning happens only through the native setup engine; Python probes no component.
- Census review reuses the existing host session (`profile_censo_*`, `native/desktop/src-tauri/src/shell/user_profile/censo.rs`) and the existing review band (`native/desktop/frontend/src/components/profile/ProfileSync.tsx`, `native/desktop/frontend/src/shell/profileCenso.ts`); it is not reimplemented. That one census flow is reachable from four entries: a global command palette action available on every page, the user profile page, the Modelo page and the AEAT sync page's census area.
- Amends `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr` (AEAT sync views), `2026-10-04-desktop-shell-adr` (AEAT sync run family, census entries and the census band's last capture time) and `2026-08-08-sync-control-surface-adr` (stop between items, desktop progress and last-sync provenance for every AEAT area); each amendment is part of its record's body, dated 2026-10-29. `2026-10-27-sede-browser-adr` is unchanged: opening a notification in the Sede view opens the panel at its own start page.

## Implementation

We will add one backend read and a host-run area queue, and build the page on them.

**Backend (the only Python).**

- `live.sync.status`: registered read, no effect, no network, all frontends. It extends `read_local_aeat_sync_workspace_projection` with IVA wallet, Borrador 100 and identity-check sources and composes only the stores it needs: latest censal observation, filed observations and their sync-run record, latest notification snapshot, IVA wallet history, latest active Borrador, and the latest verify observation for the profile's own tax number resolved in the worker. Per area it returns a closed state (`never_brought`, `current`, `possibly_stale`, `unavailable`), the last successful capture instant, the last attempt and its outcome where a sync-run record exists, and product-given counts (unread notifications; filed periods matched, AEAT-only, local-only, differing). It also serves the year choices for filed declarations and the IVA wallet. The staleness horizon per area is backend-owned data with these defaults, ruled by the owner on 2026-10-29: notifications 7 days, IVA wallet 30 days, census, filed declarations and identity checks 90 days. An area becomes `possibly_stale` once its last successful capture is older than its horizon.
- `output_root` becomes optional on `live.filed-capture.bulk`, `live.filed-history.pull` and `live.iva-wallet.history-capture`; the worker defaults it to the setting the CLI uses today, and the CLI drops its own default.
- `nif` becomes optional on `live.verify.nif-iva` and `live.verify.tgvi`; omitted, the worker checks the profile's own taxpayer number.
- Live captures report an ended AEAT session as a distinct typed refusal detail, separate from navigation failures and the unread-notification guard.

**Host (`native/desktop/src-tauri/src/shell/aeat_sync/`).** Named commands only: `aeat_sync_status`; `aeat_sync_prepare` (the browser row from the setup engine and AEAT access readiness); `aeat_sync_sign_in` (`auth.session.acquire` with the profile's configured method, reusing a valid session, including one made in the Sede view); `aeat_sync_start` (selection: areas, years, optional forms, dry run); `aeat_sync_progress`; `aeat_sync_observe` and `aeat_sync_unobserve` (a `Channel<()>` cue as for census); `aeat_sync_stop`; `aeat_sync_retry` (one area or item, person-initiated); `aeat_sync_notifications` (rows with read state, without ids); and `aeat_sync_borrador_import` (a native file token to `live.borrador.100.import`). The run lives in `ProfileHost` beside `censo`, reattaches on a repeat start, survives page navigation, and is discarded on sign-out, profile change and window close.

**Run model.** Areas run in a fixed order: census, identity checks, notifications, IVA wallet, filed declarations. Each area is one or more items. Filed declarations are `live.filed-discover` over the chosen range, then one `live.filed-capture.bulk` per year with optional forms. IVA wallet is `live.iva-wallet.history-capture` over the chosen years. Census starts the existing census session; once it reaches review the queue moves on and the review waits in the results. Stop lets the in-flight item settle and starts nothing further; untouched items show as not started. A wait past `SETTLE_LIMIT` keeps the item running; only a lost reply, an `unknown` effect or a host restart makes it unknown. Progress is item-level, refined within a year by the observation event cursor where the operation emits events. Dry run applies only to filed declarations, reads AEAT and saves nothing; the other areas are excluded from a dry run.

**Outcomes.** Each item settles to `brought`, `nothing_found`, `failed` (with the product's reason) or `unknown`; an area takes the worst of its items, and brought-with-failures is shown as such. Outcome classification is host-side: the host maps each admitted operation's terminal state, effect and typed count fields through one closed table tested against the manifest; the live results gain no shared outcome field. A session-ended refusal pauses the run at that item; after sign-in the run resumes from the first item not brought and never re-runs an unknown one.

**Preflight and sign-in.** Before sign-in the page reads the browser row. Missing, stale, failed or blocked shows the component's sentence and runs the setup engine inline (`desktop_setup_start` for `browser`), resuming when the row is ready. Missing AEAT access opens the existing access editor (`profile/aeat-access`). Cl@ve móvil shows a waiting-for-approval state while acquisition runs.

**Results.** Census: the shared review band. Filed declarations: the matching rows from `live.sync.status`. Notifications: rows with read state, a legal-receipt warning that opening an unread notification at AEAT may count as receiving it, and an action that opens the Sede view at its own start page, with no deep link; this page fetches no notification document. Borrador 100 is updated only by importing a PDF and is excluded from "everything".

**Owner rulings, 2026-10-29.** The four backend changes above are accepted in scope. Stop takes effect after the current step; no cooperative cancel is added. Staleness defaults, census entries, host-side outcome classification, the Sede start-page action and Borrador handling are as stated in this record.

**Verified hypotheses, 2026-10-29.** The census session can await review while other areas run. While it waits it holds no AEAT acquisition lock, browser or profile write lock: its conflict lease is keyed on its own definition and subject (`src/cadrumo/application/operations/persistence/leases.py:23`), its browser closes before the review is published (`src/cadrumo/application/user_profile/censal_operation.py:520`), the profile write lock is taken only at apply (`censal_operation.py:623`), and the host's `profile_censo_start` releases its serial lock once submitted (`native/desktop/src-tauri/src/shell/user_profile/censo.rs:264`). The AEAT acquisition lock is held only while a session is being acquired and refuses a concurrent acquirer at once (`src/cadrumo/application/auth/acquisition_lock.py:288`), so the run signs in before its first item and runs its items one at a time. `live.filed-discover` yields a flat list of (modelo, ejercicio) pairs that may differ by year (`src/cadrumo/application/live/filed_read_operation.py:144`). `live.filed-capture.bulk` takes a year range and an optional modelo list and captures their Cartesian product (`src/cadrumo/application/live/filed_bulk_capture_operation.py:49`, `src/cadrumo/application/live/filed_data_capture.py:909`), so each per-year item submits `year_from` and `year_to` equal to that year and `modelos` set to the forms discovered for that year, narrowed by the person's chosen forms; the discover result is never passed as one multi-year range.

## Rationale

The status read is the smallest backend addition that removes domain judgement from the window and serves the same answer to the CLI and TUI, while reusing the reader `workbench.generation` already trusts. A host queue over existing per-area operations gives stop and resume points without a new uncancellable backend workflow, and per-year filed items make stop, progress and resume meaningful. Each other backend change removes a value the window must not hold: a path, a tax number, or a message to parse.

## Consequences

- The page can say "may be out of date" with the backend's reason, and the census band can show its last capture time.
- Stop takes effect after the current step: an in-flight AEAT request finishes first. Adding cooperative cancel to the live captures would need a new decision.
- Borrador 100 has no capture operation; its area is updated by importing a downloaded PDF and is not part of "everything".
- Four contract changes to existing operations require manifest regeneration and CLI parity checks.
