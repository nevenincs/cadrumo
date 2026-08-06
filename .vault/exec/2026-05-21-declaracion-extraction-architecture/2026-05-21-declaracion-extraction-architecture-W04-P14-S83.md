---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-07-17'
body_hash: 'sha256:875d3f8ac5cd4cfde1e5b699d482e2bd2ef460d6f3ba0b7f545fb913a02c3418'
step_id: S83
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P14.S83 - M232 dead-stub replacement

## Outcome: Already correct — no action needed

Both M232 revisions (2016-2017 and 2018-y-siguientes) already have
functional `named_label` extraction profiles. Each profile targets:

- `decl.ejercicio` — `named_label`, `value_kind=amount`
- `decl.tipo-ejercicio` — `named_label`, `value_kind=enum`
- `decl.cnae` — `named_label`, `value_kind=text`

No dead `decl.*` slug stubs exist. No action needed.
