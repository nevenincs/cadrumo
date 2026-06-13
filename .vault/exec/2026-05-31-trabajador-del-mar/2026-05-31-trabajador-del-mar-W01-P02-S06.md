---
step_id: "S06"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P02.S06 step record

## Step

Add DA 41 binding entry (inactive_pending_eu_clearance) to trabajador_del_mar.toml.

## Files Touched

- `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml` — added DA 41 inactive binding entry.

## Commit

`37f4c7b4d` — feat(maritime-worker): DA 41 inactive binding entry (S06)

## Binding Entry

- id: `da41-tuna-fleet-inactive`
- status: `inactive_pending_eu_clearance`
- exempt_fraction: `0.50`
- selector: worker_class=trabajador_del_mar, tuna_fleet=true, pending_eu_clearance=true

## BOE Citations

- Ley 35/2006 DA 41 BOE-A-2006-20764 — 50% exemption for tuna fleet on Spanish-flagged vessels fishing outside EU waters. INACTIVE pending EU state-aid clearance.
- Ley 6/2018 BOE-A-2018-9268 — Ley de PGE 2018 that introduced DA 41 into Ley 35/2006, conditioned on EU clearance not yet granted as of 2024.

## Outcome

DA 41 binding entry modelled as inactive. The W02 engine must raise a typed error (MaritimeExemptionInactiveError) if da41_eligible resolves True at runtime; it must never silently produce output. TOML is valid.
