---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step9-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- No findings.
- Reviewer confirmed the VAT casilla bridge deletion is complete for this
  slice: `_modelo_303_mapping.py` and its tests are deleted, `aeat.domain.vat`
  no longer exports or imports the bridge names, and the deletion gate checks
  both physical absence and public-surface absence.
- After review, the gate was strengthened to also assert
  `importlib.util.find_spec("aeat.domain.vat._modelo_303_mapping") is None`.

Residual risk:

- The retained VAT catalogue still contains high-level Modelo 303 filing
  guidance and `declares_in_modelos` metadata. No remaining
  VAT-category-to-Modelo-303-casilla projection was found. Registry-backed
  Modelo 303 export/casilla binding remains future work.
