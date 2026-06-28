---
step_id: "S04"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P02.S04 step record

## Step

Create trabajador_del_mar.toml with Art. 7.p) binding entry.

## Files Touched

- `src/aeat/_data/registry/aeat/categories/trabajador_del_mar.toml` — created with Art. 7.p) binding entry.

## Commit

`369250d77` — feat(maritime-worker): Art. 7.p) exemption binding entry (S04)

## Binding Entry

- id: `art-7p-foreign-work`
- status: `active`
- annual_cap_eur: `60100`
- formula: `min(annual_salary / 365 * qualifying_days, 60100)`
- selector: worker_class=trabajador_del_mar, vessel_flag=foreign, waters_type=international

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — full exemption conditions including annual cap and day-rate formula, confirmed by TEAR Galicia December 2024, extended by Supreme Court April 2025.

## Outcome

Art. 7.p) binding entry created with required fields and BOE-grounded legal_refs. TOML is valid.
