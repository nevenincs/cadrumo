---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S13'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# `live-censo-calendar-reconciliation` `W05.P05.S13` exec - authenticated live surface proof

## Scope

Step `W05.P05.S13` - Record authenticated live all-model filing, expedientes, notifications, and calendar proof; `src/aeat/entrypoints/cli/_app_live.py`, `src/aeat/entrypoints/cli/_app_live_payloads.py`, `src/aeat/entrypoints/cli/_overview.py`.

## Description

- Reused the fresh password-backed profile created under W04.P04.S09 and completed Cl@ve Móvil authentication.
- Confirmed the live session persisted and the authenticated identity matched the profile NIE.
- Ran live censo, filed history, notifications, expedientes, justificante-list, and calendar commands.
- Hardened `app live filed list` so an all-model listing reports per-model AEAT/register failures instead of aborting the entire run.

## Outcome

- `uv run aeat --format json config profile censo pull` reached AEAT G313 and refused because the sede did not return a legible censo for the authenticated profile.
- `uv run aeat --format json app live filed list --modelo 303 --from-year 2025 --to-year 2026` succeeded with `row_count=0`.
- `uv run aeat --format json app live notifications pull` succeeded, persisted snapshot `8202e7fe300213085c7b78fd832c881481d62d315db3417170a9ef64b62e14e4`, and captured `row_count=1`.
- `uv run aeat --format json app live filed list --from-year 2026 --to-year 2026` succeeded after hardening with `row_count=0`, `failed_count=1`, and a `721` failure because AEAT did not offer that modelo in the declarations register.
- `uv run aeat --format json app live filed pull-all --from-year 2026 --to-year 2026 --output-root var/aeat/live-user-smoke/filed-declarations` succeeded with `captured_count=0`, `failed_count=8`, and no justificante artefacts because no filed declarations were returned.
- `uv run aeat --format json app live expedientes pull-all --from-year 2026 --to-year 2026` succeeded with `captured_snapshot_count=1`, `declaration_count=0`, and `failed_count=1` for `721`.
- `uv run aeat --format json app live justificante list` succeeded with `count=0`.
- Final `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` succeeded with Modelo `100`, `303`, `390`, and `721` obligation rows, every filing row carrying `justificante_required=true`, `justificante_verified=false`, and `aeat_submission_state=not_observed`. The captured AEAT notification projected as a calendar `message` event dated `2026-06-03`.

## Verification

- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_payloads.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py -q` passed: 3 passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -m integration -q` still has two pre-existing Period type drift failures unrelated to this S13 filed-list change: `Borrador100SnapshotService.capture(period='0A')` and `IvaRemoteStateAcquisitionReport(target_period='2T')`.

## Notes

- W03.P03.S06/S07 and W04.P04.S10/S11 remain open for censo reconciliation because live G313 did not return a legible Modelo 036/censo snapshot.
- The authenticated live proof now distinguishes: no AEAT filed declarations observed, no justificantes available to pull, one AEAT notification captured and projected into the calendar.
