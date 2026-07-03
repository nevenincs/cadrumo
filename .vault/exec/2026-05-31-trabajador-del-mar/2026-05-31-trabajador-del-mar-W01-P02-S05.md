---
step_id: "S05"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-06-29'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P02.S05 step record

## Step

Add REBECA binding entry to trabajador_del_mar.toml.

## Files Touched

- `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml` — added REBECA 50% exemption binding entry.

## Commit

`f3484e673` — feat(maritime-worker): REBECA 50% exemption binding entry (S05)

## Binding Entry

- id: `rebeca-50pct`
- status: `active`
- exempt_fraction: `0.50`
- selector: worker_class=trabajador_del_mar, vessel_registry in [REBECA, rebeca_eu_eea, scheduled_canary_route]

## BOE Citations

- Ley 19/1994 Art. 73.2 BOE-A-1994-15794 — REBECA 50% exemption on gross navigation employment income
- Ley 19/1994 Art. 73.3 BOE-A-1994-15794 — conditions: REBECA-enrolled vessel, employer withholding adjustment
- Ley 19/1994 Art. 75.1 BOE-A-1994-15794 — 2021 extension to EU/EEA sister-registry vessels
- Ley 19/1994 Art. 75.3 BOE-A-1994-15794 — employer withholds on 50% of gross; exempt 50% excluded from Modelo 111 base

## Outcome

REBECA binding entry added with 4 legal_refs covering Arts. 73.2, 73.3, 75.1, 75.3. TOML is valid.
