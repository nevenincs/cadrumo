---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0aced24328235aa63e503f49f062d3f706b554bf7468cce4b1b978fc297006e6'
step_id: 'S13'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Re-adjudicate Modelo 322 deadlines, remove stale 2023 copies, and materialise every supported periodic row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/322/`

## Description

- Discover the canonical deadline authority with Vaultspec RAG before editing.
- Re-adjudicate all twelve Modelo 322 ejercicio-2022 presentation windows against official AEAT calendars.
- Materialise the nine absent monthly coordinates beneath the revision selected by `select_revision`.
- Correct June's presentation close from 30 July to the published 1 August extension.
- Preserve an absent payment cutoff because AEAT's 2022 domiciliation table names monthly Modelos 303 and 353, not Modelo 322.
- Bundle and catalogue the official AEAT 2022 taxpayer calendar and cite the existing 2023 calendar for December's following-January close.
- Extend construct citation closure and add exact date, evidence, ownership, and authority-projection regressions.

## Outcome

The `2008-2022` revision now carries exactly one window for each selected token `01` through `12` for filing year 2022. Every coordinate resolves back to that same revision through the canonical `select_revision` authority, and `ValidatedRegistryAuthority.deadline_windows` projects exactly twelve M322 rows for 2022. All twelve rows explicitly leave `payment_cutoff_on` absent rather than copying an unsupported cutoff from a different modelo.

Focused cold validation and the complete M322 registry test module passed with 13 tests. Ruff passed on the changed Python surface.

## Notes

Vaultspec RAG semantic queries were `M322 monthly filing deadline windows canonical revision ownership` against code and `deadline window revision authority M322 monthly materialization` against ADR, research, and plan records. Exact-symbol confirmation located `select_revision` in `_temporal.py`, the canonical projection in `_authority.py`, `Period` and `registry_period_kind` in core `_period.py`, and `resolve_filing_window` in deadlines `_plazo.py`. The engine's public `deadline_windows` method was inspected and confirmed to be a read-only delegation to the registry authority rather than a second selector. No new resolver, period parser, cadence map, deadline catalogue, or selection algorithm was introduced.

The stale pre-existing test claim that revision `2008-2022` began in 2008 was aligned with the current authoritative revision span, which explicitly selects only 2022. No 2023 row was removed: the remaining 2023 rows occur only under the canonical `2023` owner, so deleting them would have created under-declaration rather than removing a stale copy.
