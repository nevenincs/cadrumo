---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S32
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P10.S32 - M840 named_label extraction profile

## Outcome: Profile authored (combined with S26)

See S26 record. The `modelo-840-declaracion-pdf` profile was authored in
`src/aeat/_data/registry/aeat/modelos/840.toml` under
`revisions."2003-y-siguientes"`. Targets:

- `decl.tipo-declaracion` — `named_label`, `value_kind=enum`
- `decl.ejercicio` — `named_label`, `value_kind=amount`

Source grounding: `aeat-dr-840`, `boe-modelo-840-2003-form`.

**PROVISIONAL LABEL PATTERNS**: The corpus artefact is a diseño de registro (EDI
record-layout spec), NOT a real printed-declaración-form PDF specimen. The
`label_pattern` values were derived from registry casilla LABEL fields and are
unverified guesses. Verification requires a W05 round-trip parse test against a
real M840 printed-form PDF. No such PDF exists in the corpus yet.

## Commit

`3af7ea87e` — W04: author named_label declaracion_pdf profiles for M036, M347, M369, M840
