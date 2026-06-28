---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W37.P185'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W37.P185`

Thin-CLI-exposure phase for the festivos service. The substrate has
no direct operator-facing CLI verb; the accepted consumption path is
via the deadline / agenda surfaces that the ADR delegates to W53.

## Description

Per the festivos-deadline-shift ADR, the festivos service is a
foundation module that other workflow surfaces consume. The two
accepted consumers are:

- `aeat app overview calendar` — owned by W53 (overview / calendar
  surface). Will render `DeadlineShift`-annotated obligations so
  the operator sees the original close date, the adjusted close
  date, and the shift reason side-by-side.
- `aeat app overview agenda` — also owned by W53. Will sort
  obligations by adjusted close date and explain shifts in the
  per-row reason column.

W37 therefore lands no new Typer command directly; instead it lands
the substrate and the regression guards that make the W53 surface
correct on arrival. The boundary tests in P182 / P183 enforce:

- No parallel festivos implementation may sit inside the CLI tree.
- No hardcoded festivos table may live inside the CLI tree.

The argument-parsing, backend-delegation, `_emit` rendering, and
central command-error-boundary contracts are satisfied transitively
when W53's `aeat app overview calendar` and `aeat app overview
agenda` handlers consume the substrate. The festivos service exposes
no flags of its own at the CLI layer in this wave.

Help-text correctness is enforced at the W53 level by the overview
ADR; W37 contributes no help text of its own.

`DeadlineShift`, `CCAA`, `shift_deadline`, `is_business_day`,
`next_business_day`, `load_holiday_calendar`, and the
`MODELOS_WITHOUT_SHIFT` exception list are exported from
`aeat.domain.deadlines` so the W53 overview surface can consume them
without reaching into private modules.

Closed plan rows: `W37.P185.S1105`, `W37.P185.S1106`,
`W37.P185.S1107`, `W37.P185.S1108`, `W37.P185.S1109`,
`W37.P185.S1110`.

## Tests

No new CLI tests are landed in this phase because no new CLI verb is
exposed. The two boundary regression guards covered in P182 / P183
remain the enforced contracts for the CLI tree.
