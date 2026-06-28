---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S89
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W05.P15.S89 - correct modelo-111 rule-delta reference extractor-class prose

## Outcome

`.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` corrected.

The Audit trail section had a single 2026-04-27 entry stating that sibling
`Modelo111V2024Extractor` / `Modelo111V2026Extractor` classes were registered in
`_extractors/__init__.py`. A new dated row (2026-05-21) was appended to the audit
table recording that those extractor classes were subsequently deleted; declaración
extraction is now driven by registry `declaracion_pdf` extraction profiles. Reference
to `2026-05-21-declaracion-extraction-architecture-adr` added.

The historical 2026-04-27 row was preserved intact; only an additional audit row
was added.
