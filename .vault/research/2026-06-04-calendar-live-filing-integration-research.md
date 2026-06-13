---
tags:
  - '#research'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-04-12-deadline-engine-adr]]'
---

# `calendar-live-filing-integration` research: `calendar, filed history, justificantes, and AEAT messages`

This research grounds the feature gap where the profile-derived obligation calendar, live AEAT filing-history capture, and live notification/message capture exist as separate surfaces but do not produce one operator-facing calendar.

## Findings

- The overview calendar is already a typed application projection in `aeat.application.overview`. It derives obligations from the profile via `DeadlineEngine`, applies applicability filtering, and shifts close dates through the holiday calendar. The current output is still obligation-centric: it has deadline rows, warnings, completeness, and suppressed obligations, but no independent event rows for filed declarations or messages.
- The CLI surface `aeat app overview calendar` is intentionally local-only. It reads the active profile, derives `TaxpayerProfile`, calls `build_overview_calendar`, and emits the typed envelope. This is the right integration point for already-persisted live-read state, but it must not contact AEAT from the overview command.
- Filed declaration live reads already belong under `aeat app live filed`, per the accepted app-registry-boundary ADR. The existing backend can list filed declarations for one modelo/year range, capture filed declaration artefacts for one modelo/year, and capture source filings required by registry cross-filing dependencies.
- The current `filed list` CLI already accepts an omitted `--modelo` and then iterates all registry modelos for the requested year range. The capture path is narrower: `filed capture` requires one modelo and one year, so there is no single backend/command that pulls justificantes and declaration artefacts for every registry modelo across a year range.
- The `ExpedientesService` persists AEAT declaration-register snapshots as encrypted bucket-scoped secure objects. The rows carry modelo, ejercicio, period, expediente id, AEAT status, presentation timestamp, and whether justificante/submitted/declaration-copy links exist.
- The `NotificationsService` persists DEHU notification snapshots as encrypted bucket-scoped secure objects. Rows carry certificate id, notification/communication type, concept, titular/destinatario data, emission date, notification date, read state, and source URL.
- The bucket event history ADR already reserves live snapshot events, including `live.notifications.snapshot_captured`, `live.expedientes.snapshot_captured`, and `live.filed.capture_created`. The current services are persistence-focused; the overview calendar can project from persisted snapshots without depending on event history as authoritative state.
- The filing calendar must stay honest about remote coverage. The AEAT declaration-register adapter is implemented against the `Consultar declaraciones presentadas` surface and queries one modelo/year at a time. The code supports every modelo present in the local registry only to the degree AEAT offers that modelo in the live form and the registry has extraction support. Bulk capture therefore needs a failure ledger, not a silent "all modelos succeeded" claim.
- `vaultspec-rag` is installed, but the local Qdrant index was locked by another process in this shared worktree during this research run. The fallback research path used `rg` over `.vault`, source, and tests without stopping the other process.

## Recommendation

- Keep `build_overview_calendar` pure and additive. Add a typed calendar-event projection to the overview application layer, with helpers that convert already-persisted expedientes and notifications snapshots into calendar events.
- Wire `aeat app overview calendar` to include local persisted live-read events from the active bucket by default, while preserving the no-remote-contact invariant.
- Add a backend `capture_filed_data_bulk` application service and `aeat app live filed capture-all` CLI command. It should iterate registry modelos and years under one live-read/auth session, attempt filed declaration artefact capture, persist successful calculation observations, and report per-declaration failures explicitly.
- Add focused real-behavior tests for the pure projection helpers, local snapshot persistence integration, CLI payload schema, and bulk report failure accounting. Live AEAT traversal remains gated by existing live-read controls and is not exercised by default unit tests.
