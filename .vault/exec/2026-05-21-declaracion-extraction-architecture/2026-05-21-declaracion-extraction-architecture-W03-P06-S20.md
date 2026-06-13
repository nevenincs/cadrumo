---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S20'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P06.S20`

BLOCKED — M180 `declaracion_pdf` profile cannot be authored in W03: no fixture PDF exists to ground the printed label targets, and the registry casilla IDs cannot support `numeric_casilla` matching.

## Description

Execution halted per plan mandate: "If a modelo's real casilla set cannot be confidently sourced from the corpus, STOP and report."

**Blocker 1 — registry structural gap:** M180 casilla IDs are electronic file-record position ranges (`"136-144"`, `"145-160"`, `"161-175"`). These position strings are never printed on the declaration form. `numeric_casilla` strategy cannot work. A `declaracion_pdf` profile must use `named_label` strategy.

**Blocker 2 — no fixture PDF:** No M180 declaración PDF justificante exists in `src/aeat/tests/fixtures/justificantes/180/` or anywhere in the test corpus. The AEAT Diseño de Registros corpus for M180 contains 3 PDFs, all of which are electronic file-structure specifications (record design documents), not printed form samples. Without a real printed-form sample, the `label_pattern` values for the `named_label` targets cannot be grounded against actual PDF text.

The existing `export_record` profile (`surface = "export_record"`) correctly uses `named_label` strategy with 3 summary targets (`Numero total de perceptores`, `Base retenciones…`, `Retenciones e ingresos a cuenta total`). A `declaracion_pdf` profile would likely use the same 3 summary labels, but the printed form labels may differ from the electronic file labels — this cannot be confirmed without a fixture PDF.

**Recommendation:** Obtain a sample M180 declaración PDF justificante (the PDF issued by AEAT when a Modelo 180 is presented). Once obtained, add it to the fixtures corpus and author the `declaracion_pdf` profile in W04 alongside the other `named_label` profiles, using the confirmed printed labels. Flag the follow-up as requiring a sample PDF acquisition step.

## Tests

No files modified. Baseline test suite (41/41 committed registry, 7/7 parser boundary) confirmed passing before halt.
