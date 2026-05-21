---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
step_id: S28
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P10.S28 - M036 named_label extraction profile

## Outcome: Profile authored

Authored `modelo-036-declaracion-pdf` extraction profile in
`src/aeat/_data/registry/aeat/modelos/036.toml`
under `revisions."2025-02-03-y-siguientes"`:

Targets (2 casillas):
- `decl.event-kind` — `named_label`, `value_kind=enum`,
  `label_pattern = 'Tipo\s+de\s+declaraci[oó]n\s+censal'`
- `decl.vigencia-2025` — `named_label`, `value_kind=text`,
  `label_pattern = 'Vigencia\s+normativa\s+desde'`

Added `modelo-036-extractor` application link (surface=extractor).
Wired both into the `modelo-036-census-foundation` construct.

Source grounding: `aeat-dr-036-2025`, `aeat-modelo-036-procedure`
(Diseño xlsx 2025 + instructions HTML in corpus).

## Commit

`3af7ea87e` — W04: author named_label declaracion_pdf profiles for M036, M347, M369, M840
