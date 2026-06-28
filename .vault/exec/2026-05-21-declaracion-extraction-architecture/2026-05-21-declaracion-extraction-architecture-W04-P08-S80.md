---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S80
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P08.S80 - Classification: dead-stub modelos target resolution

## Per-modelo classification

### M184 (2015-y-siguientes)
- `decl.ejercicio` (year) → `named_label`, `value_kind=amount`
- `decl.tipo-declaracion` (text) → `named_label`, `value_kind=enum`
- **STATUS: ALREADY AUTHORED** — profile `modelo-184-declaracion-pdf` exists and
  is functional. No action needed.

### M193 (2024-y-siguientes)
- `decl.total-perceptores` (money) → `named_label`, `value_kind=amount`
- `decl.base-total` (money) → `named_label`, `value_kind=amount`
- `decl.retenciones-total` (money) → `named_label`, `value_kind=amount`
- **STATUS: ALREADY AUTHORED** — profile `modelo-193-declaracion-pdf` exists and
  is functional. No action needed.

### M232 (both revisions)
- `decl.ejercicio` (year) → `named_label`, `value_kind=amount`
- `decl.tipo-ejercicio` (text/enum) → `named_label`, `value_kind=enum`
- `decl.cnae` (text) → `named_label`, `value_kind=text`
- **STATUS: ALREADY AUTHORED** — profiles for both revisions exist and are
  functional. No action needed.

### M347 (2008-y-siguientes) — profile removed by W02 review-fix
- `decl.ejercicio` (year) → `named_label`, `value_kind=amount`
- `decl.tipo-declaracion` (text) → `named_label`, `value_kind=enum`
- **STATUS: NEEDS AUTHORING** — W04.P14.S84

### M349 (2020-y-siguientes)
- `decl.numero-operadores` (money) → `named_label`, `value_kind=amount`
- `decl.importe-operaciones` (money) → `named_label`, `value_kind=amount`
- `decl.numero-rectificaciones` (money) → `named_label`, `value_kind=amount`
- `decl.importe-rectificaciones` (money) → `named_label`, `value_kind=amount`
- **STATUS: ALREADY AUTHORED** — profile `modelo-349-declaracion-pdf` exists and
  is functional. No action needed.

### M720 (2013-y-siguientes)
- `decl.ejercicio` (year) → `named_label`, `value_kind=amount`
- `decl.tipo-declaracion` (text) → `named_label`, `value_kind=enum`
- **STATUS: ALREADY AUTHORED** — profile `modelo-720-declaracion-pdf` exists and
  is functional. No action needed.

### M840 (2003-y-siguientes) — profile removed by W02 review-fix
- `decl.tipo-declaracion` (text) → `named_label`, `value_kind=enum`
- `decl.ejercicio` (year) → `named_label`, `value_kind=amount`
- **STATUS: NEEDS AUTHORING** — W04.P09.S26 / W04.P10.S32

## Action

No code changes. This Step is a classification record only.
