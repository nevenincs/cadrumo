---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S19'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P06.S19`

BLOCKED — M303 `declaracion_pdf` profile cannot be authored in W03 due to casilla ID / form number mismatch in the registry.

## Description

Execution halted per plan mandate: "If a modelo's real casilla set cannot be confidently sourced from the corpus, STOP and report."

**Blocker:** The M303 registry exclusively uses semantic slug casilla IDs (`iva.repercutido.general`, `iva.cuota-devengada-total`, etc.). The `numeric_casilla` match strategy requires that the `casilla_id` in the extraction profile target matches text printed literally on the PDF form (the regex anchors `re.escape(casilla_id)` at line start). No M303 casilla ID in the registry equals a printed form number. The printed form uses boxes `01`–`110`; the registry has no casilla with those IDs.

A minimal approach of targeting only the 4 compensation/result casillas whose `number` fields are numeric (`iva.resultado` with `number = "69"`, etc.) would not work either — the extraction would anchor on `iva.resultado` not `69`.

**Required prerequisite:** The M303 registry must be extended to add casilla entries with numeric IDs matching the printed form boxes (as M111 does with `id = "01"` .. `id = "30"`). This is a registry restructure step outside the scope of W03's "author extraction profiles" mandate.

**Recommendation:** Add a follow-up task to extend M303 with numeric printed-form casilla IDs (covering at minimum the result chain: 27=total devengada, 45=total deducible, 46=régimen general, 69=resultado, 78=compensación aplicada, 87=compensación pendiente, 110=compensación anterior periods). Once those IDs exist in the registry the `numeric_casilla` profile becomes straightforward.

## Tests

No files modified. Baseline test suite (41/41 committed registry, 7/7 parser boundary) confirmed passing before halt.
