---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S90
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W05.P15.S90 - correct _detect.py module docstring

## Outcome

`src/aeat/adapters/inbound/declaracion/_detect.py` module docstring corrected.

The original closing sentence of the module docstring read:

> the revision tag does not bind a Python extractor class.

This was a negative statement that implicitly referenced the deleted extractor
mechanism. Replaced with a positive accurate description:

> the revision tag selects the registry `declaracion_pdf` extraction profile
> for the matched modelo and ejercicio.

No behaviour change. Ruff clean. All 16 declaracion adapter tests pass.
