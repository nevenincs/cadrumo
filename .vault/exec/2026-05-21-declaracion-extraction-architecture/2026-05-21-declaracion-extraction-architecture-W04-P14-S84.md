---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S84
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P14.S84 - M347 dead-stub replacement

## Outcome: Real named_label profile authored

The W02 review-fix had removed the dead profile from
`src/aeat/_data/registry/aeat/modelos/347.toml`.

Authored `modelo-347-declaracion-pdf` extraction profile under
`revisions."2008-y-siguientes"`:

Targets (2 casillas):
- `decl.ejercicio` — `named_label`, `value_kind=amount`,
  `label_pattern = 'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'`
- `decl.tipo-declaracion` — `named_label`, `value_kind=enum`,
  `label_pattern = 'Tipo\s+de\s+declaraci[oó]n'`

Added `modelo-347-extractor` application link (surface=extractor).
Wired into the `modelo-347-informative` construct.

Source grounding: `aeat-dr-347-2025`, `aeat-modelo-347-procedure`
(Diseño PDFs 2025 + procedure HTML in corpus).

**PROVISIONAL LABEL PATTERNS**: The corpus artefacts are diseño de registro files
(EDI record-layout specs) and procedure HTML, NOT a real printed-declaración-form PDF
specimen. The `label_pattern` values were derived from registry casilla LABEL fields
and are unverified guesses. Verification requires a W05 round-trip parse test against
a real M347 printed-form PDF. No such PDF exists in the corpus yet.

## Commit

`3af7ea87e` — W04: author named_label declaracion_pdf profiles for M036, M347, M369, M840
