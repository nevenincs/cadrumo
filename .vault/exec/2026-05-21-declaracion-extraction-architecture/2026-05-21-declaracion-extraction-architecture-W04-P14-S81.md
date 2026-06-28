---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S81
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P14.S81 - M184 dead-stub replacement

## Outcome: Already correct — no action needed

`modelo-184-declaracion-pdf` was already authored as a functional
`named_label` profile during a prior campaign wave. The profile targets:

- `decl.ejercicio` — `named_label`, `value_kind=amount`,
  `label_pattern = 'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'`
- `decl.tipo-declaracion` — `named_label`, `value_kind=enum`,
  `label_pattern = 'Tipo\s+de\s+declaraci[oó]n'`

No dead `decl.*` slug stubs exist. The `modelo-184-extractor` application
link is wired. No action needed.
