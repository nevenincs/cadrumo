---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:b07ad31641498597c84dc9c0a043af3f86247843eaf28154c4bae0342be64d3d'
step_id: 'S438'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Resolve the three M200/2024 casillas the row-splitting parser had mis-read as structural. Joining record-design rows before matching shows DP200014B:00599 names exactly one cell on its own page, and the two symbolic identifiers are calculation-only casillas -- one internal_only and computed, one manual and manual-sourced -- which have no design row by construction and take a label describing what they are rather than one claiming design authority.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`

## Changes

Unlabelled M200/2024 casillas: 7 -> 4. Three of the four I had called structural
were not.

DP200014B:00599 was held because its number "repeats on its own page". It does
not. That reading came from the same line-splitting artefact S437 found: a design
cell whose text wraps is read as several fragments, and the fragments look like
repeated occurrences. Joining rows first, the page names exactly one cell, and
the same cell in both the 2024 and 2025 designs.

The two symbolic identifiers are a different thing again, and calling them
unresolvable was wrong. DP200014:bin-aplicada-maxima is internal_only with
input_kind computed and a formula: it is the art. 26.1 compensation ceiling the
engine derives, not a box on the form. DP200014:SAL_RESERVA_DOTACION is
manual-sourced and documented as the single calculation-only casilla carrying
the Ley 44/2015 art. 14 reduction. Neither has a record-design row BY
CONSTRUCTION, so waiting for one to appear would wait forever.

They take a label describing what they are, written from their own declared
semantic role and cardinality reason, and deliberately NOT claiming design
authority: no pin covers them and none should, because there is no official cell
to pin. That is the honest shape for a calculation-only casilla -- the operator
still needs to know what the row is, and the label says so without implying the
AEAT printed it.

Both label gates pass. The runtime localization gate is down to 4 casillas.

## Notes

STILL BLOCKED, 4, and all four need a registry decision rather than a locale
one.

01264, 01265 and 01266 declare "2025 innovacion tecnologica (IT)" while the only
cell bearing those numbers, in the 2024 design and absent from the 2025 one,
reads "2024 Reconstruccion de la Piscina Historica cubierta de saltos del Club
Natacio Barcelona (CNB)". Either the section is wrong and these are the Club
Natacio rows, or the numbers are wrong and the IT rows live elsewhere.

DP200018:00588 resolves to one cell, "Deducc. para incentivar
determ.actividades - Total - Aplicado en esta liquidacion", while its
declaration says "liquidacion_iv / otras_deducciones". Those are plausibly the
same thing described two ways -- deductions to incentivise certain activities ARE
among Liquidacion IV's other deductions -- but that is a judgement about what the
declaration means, not something the design corroborates, so it is not taken
here.
