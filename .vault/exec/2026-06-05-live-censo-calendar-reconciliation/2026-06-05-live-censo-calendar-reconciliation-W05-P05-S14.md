---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S14 - pull-only live CLI and Period-safe output

Scope: `src/aeat/entrypoints/cli/_app_live.py`, `src/aeat/entrypoints/cli/_app_live_expedientes_cli.py`, `src/aeat/entrypoints/cli/_app_live_payloads.py`.

## Description

- Verify the live filed and expedientes AEAT acquisition surfaces expose range and all-model execution through `pull` rather than `pull-all`.
- Verify CLI JSON envelopes for single and bulk filed pulls use `app.live.filed.pull` with `mode` values of `single` or `bulk`.
- Verify CLI JSON envelopes for single and bulk expedientes pulls use `app.live.expedientes.pull` with `mode` values of `single` or `bulk`.
- Exercise Period-safe CLI boundaries for calendar, borrador, justificante, filed, and expedientes payloads.
- Update the focused calendar CLI fixtures to construct `core.Period` values instead of raw period strings.

## Outcome

- Live `config profile censo pull` reached AEAT G313 and refused because no legible censo was returned for the profile identity, so live Modelo 036 reconciliation remains open.
- Live `app live filed pull --from-year 2026 --to-year 2026` succeeded under `app.live.filed.pull` with `mode=bulk`, `captured_count=0`, `failed_count=8`, and explicit failure rows for Modelos `036`, `100`, `151`, `200`, `202`, `210`, `714`, and `721`.
- Live `app live expedientes pull --from-year 2026 --to-year 2026` succeeded under `app.live.expedientes.pull` with `mode=bulk`, `captured_snapshot_count=1`, `declaration_count=0`, `failed_count=1`, and snapshot id `020d96cb26ac54d6c48abf92afc42b95ab4a6f00f63b325426cd73acfd0a3f8b`.
- Live `app live notifications pull` succeeded with one AEAT notification snapshot, snapshot id `21a3f4a3b05fde97ab2b0d01bee70942b3e9cdbf2941d9aae94362a77512d4b6`, captured at `2026-06-12T06:26:28.191253+00:00`.
- Live `app live justificante pull --modelo 303 --year 2026 --period 1T` refused because no filed declaration existed for the target period, leaving justificante verification false.
- Live single-model `app live filed pull --modelo 303 --year 2026` succeeded with `mode=single` and zero captured declarations.
- Live single-model `app live expedientes pull --modelo 303 --year 2026` succeeded with `mode=single`, zero declarations, and snapshot id `df69c783cc14751a1732a137ac5e70e81d6d03273f220b9b54d83b5e4c26685e`.
- Final live `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` generated at `2026-06-12T06:28:23.404189Z` and showed obligation rows for Modelos 100, 303, 390, and 721 plus one AEAT message event dated `2026-06-03` with reference `2699762611205`; filing evidence remained `aeat_submission_state=not_observed` and `justificante_verified=false` as expected.

## Notes

- Focused verification passed: 310 tests across overview calendar, live filed bulk capture, justificante capture/reconcile, live read subgroups, live justificante verbs, JSON schema conformance, and documented command conformance.
- Ruff passed for the touched live CLI and calendar surfaces.
- `uv run python -m aeat.locales scaffold --check` still reports pre-existing locale drift: seven missing and five extra keys in each locale catalogue. The `pull-all` locale strings are no longer present in the live CLI locale files.
