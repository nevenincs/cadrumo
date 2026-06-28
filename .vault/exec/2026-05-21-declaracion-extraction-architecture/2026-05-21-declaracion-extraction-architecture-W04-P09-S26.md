---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S26
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P09.S26 - M840 dead-stub repair

## Outcome: Real named_label profile authored

The W02 review-fix had removed the dead `declaracion_pdf` profile from
`src/aeat/_data/registry/aeat/modelos/840.toml` (it had `decl.tipo-declaracion`
with `data_type=text` but `match_strategy=numeric_casilla`).

Authored a real `named_label` profile `modelo-840-declaracion-pdf`:

- `decl.tipo-declaracion` — `named_label`, `value_kind=enum`,
  `label_pattern = 'Tipo\s+de\s+declaraci[oó]n\s+\(alta\s*/\s*variaci[oó]n\s*/\s*baja\)'`
- `decl.ejercicio` — `named_label`, `value_kind=amount`,
  `label_pattern = 'Ejercicio\s+fiscal\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'`

Added `modelo-840-extractor` application link (surface=extractor).
Wired both into the `modelo-840-iae-declaration` construct.

Source grounding: `aeat-dr-840`, `boe-modelo-840-2003-form`
(Orden HAC/2572/2003, AEAT Diseño PDF in corpus).

**PROVISIONAL LABEL PATTERNS**: The corpus artefact is a diseño de registro (EDI
record-layout spec), NOT a real printed-declaración-form PDF specimen. The
`label_pattern` values were derived from registry casilla LABEL fields and are
unverified guesses. Verification requires a W05 round-trip parse test against a
real M840 printed-form PDF. No such PDF exists in the corpus yet.

## Commit

`3af7ea87e` — W04: author named_label declaracion_pdf profiles for M036, M347, M369, M840
