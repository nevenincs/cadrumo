---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:107eb4231953f3dd88d43c4f07ba87a6363772861362b26ec179f39008e1d3b6'
step_id: 'S17'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Run every affected test module in a sequential run and record the full captured result

## Scope

- `src/cadrumo`

## Description

- Ran the broad affected tree sequentially, capturing full output to a file and reading the failure summary back from disk.
- Ran a focused owner-surface selection covering every module this work created or edited.
- Triaged every failure in the broad run against the owner surface.

## Outcome

**The owner surface is green.** Every module this work created or edited passes.

    uv run --no-sync pytest <owner surface modules> -m "unit or integration" -n 0 -q
    638 passed in 184.63s (0:03:04)

The broad run over the wider tree reports 61 failures against 6491 passes. Each was triaged and none belongs to this work:

- Eleven raise `NoRevisionForPeriodError` for Modelo 200 filing year 2024. The committed revision declares `period_selector = { year_from = 2025 }`, so that year genuinely has no revision. Nothing here touches the registry modelo tree or revision selection.
- Six fail on an `extra_forbidden` validation error for a `notificacion_estado_servicio` field present on the application-layer calendar event model but absent from the CLI payload schema. A peer's half-landed feature.
- Sixteen fail inside ledger evidence extraction with the local LLM provider reporting request failures. Environment, not code.
- The remaining conformance failures name a peer's new direct-output call, three CLI sub-verbs mounted but absent from the operator-surface contract, and a new capability row. All are surfaces this work adds nothing to.

**One failure in the broad run WAS in scope and was fixed rather than triaged away.** An attribution-entity test asserted a raw row-indexed profile path appears in a readiness refusal, which is the exact contract this work replaces. It now asserts the schema-derived label, derived from the schema rather than hardcoded.

## Verification

    uv run --no-sync pytest <affected tree> -m "unit or integration" -n 0 -q
    61 failed, 6491 passed, 1 warning in 3414.23s (0:56:54)

    uv run --no-sync pytest <owner surface> -m "unit or integration" -n 0 -q
    638 passed in 184.63s (0:03:04)

Both runs were sequential (`-n 0`), and full output was written to a file and read back rather than piped through a truncating filter.

## Notes

The broad run is reported honestly as red with an owner triage, not as green. Its red state is pre-existing peer work in flight, and absorbing it would mean editing modules belonging to active peer campaigns.
