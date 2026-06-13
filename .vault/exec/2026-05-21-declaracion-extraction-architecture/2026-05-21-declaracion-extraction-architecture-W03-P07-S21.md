---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S21'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W03.P07.S21`

ALREADY SATISFIED — M190 `declaracion_pdf` profile with real `named_label` targets was authored during W02. No change required.

## Description

Discovery sweep confirmed that the M190 `2025-y-siguientes` revision already carries a functional `declaracion_pdf` extraction profile (`id = "modelo-190-declaracion-pdf"`) with three `named_label` targets:

- `casilla_id = "decl.total-percepciones"`, `label_pattern = 'N[uú]mero\s+total\s+de\s+percepciones'`
- `casilla_id = "decl.percepciones-total"`, `label_pattern = 'Importe\s+total\s+de\s+las\s+percepciones'`
- `casilla_id = "decl.retenciones-total"`, `label_pattern = 'Importe\s+total\s+de\s+retenciones\s+e\s+ingresos\s+a\s+cuenta'`

All three targets reference real M190 casilla IDs in the registry. The profile has `confidence = "strict"`, `min_coverage = "1.0"`, `failure_semantics = "fail_hard"`. The `verification_expectations` stanza (`modelo-190-annual-summary-verification`) also correctly lists these three casillas as `computed_casillas`.

The `decl.*` stub targets that the plan's step description references were already replaced during the W02.P12.S57 TOML migration step. The dead stub profile state described in the plan's W01 discovery notes no longer exists in HEAD.

Step is closed as already-done.

## Tests

- `test_committed_registry.py`: 41/41 passed — M190 snapshot validates
- No files modified
