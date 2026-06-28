---
tags:
  - '#audit'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` Live Verification

## LIVE-001 | INFO | Read-only AEAT authentication and live pulls executed

Initial Cl@ve attempts timed out until a persisted authenticated session was established. After that, live read-only commands succeeded for filed declarations, filed artefact/justificante capture, all-model bulk capture, IVA history, remote IVA wallet state, notifications, and expedientes.

Evidence files were written under `var/aeat/live-verification`.

## LIVE-002 | INFO | Filed history and justificante artefacts pulled

`app live filed list --modelo 303 --from-year 2022 --to-year 2026` returned 14 filed Modelo 303 rows. `app live filed capture --modelo 303 --year 2024 --period 1T --limit 1` captured one filing, persisted three secure artefact refs, and produced 79 casillas plus one calculation observation key.

`app live filed capture-all --from-year 2024 --to-year 2024` queried 30 registry modelos, captured 11 observations, persisted 33 artefact refs, produced 594 casillas and 8 calculation observations, and reported 3 explicit failure rows.

## LIVE-003 | INFO | IVA aggregation/history and remote wallet state verified

`app live iva-wallet capture-history --from-year 2022 --to-year 2026` captured 12 filed Modelo 303 observations and reloaded 12 history rows. A broad combined remote-state run hit the 240 second CLI watchdog; the narrower `2026`/`2026 1T` remote-state acquisition succeeded with both `filed_history_succeeded` and `wallet_succeeded` true.

## LIVE-004 | INFO | Notifications, expedientes, and calendar aggregation verified

`app live notifications capture` persisted one notification snapshot row. `app live expedientes capture --modelo 303 --year 2024` persisted one expedientes snapshot. After the incomplete-profile event fix, `overview calendar --all-profiles` showed six filing events for 2024-2025 and one message event for 2026.

## LIVE-005 | INFO | AEAT live pytest smoke set passed

Ran the AEAT-focused live-read pytest smoke set with `AEAT_LIVE_TESTS_ENABLED=1` and `-m live_read`. Final result: 8 passed, 3 skipped. The skipped tests were live-row/session-shape skips in existing tests, not failures of the newly implemented calendar or filed-capture paths.

## LIVE-006 | INFO | Verify CLI surface exercised

`app live verify tgvi A28015865` completed successfully against a public Spanish corporate NIF. `app live verify nif-iva ESB82944547` reached AEAT but failed with an auth-tier gate: IXVI requires an AEAT authentication tier above the current Cl@ve Móvil session. This is an external auth capability boundary, not a command registration failure.
