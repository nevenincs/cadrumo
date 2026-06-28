---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S30
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P10.S30 - M369 named_label extraction profile

## Outcome: Profile authored for Esquema Union revision

Authored `modelo-369-union-declaracion-pdf` extraction profile in
`src/aeat/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml`:

Targets (2 casillas):
- `decl.ejercicio` — `named_label`, `value_kind=amount`,
  `label_pattern = 'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+autoliquidaci[oó]n'`
- `decl.periodo` — `named_label`, `value_kind=text`,
  `label_pattern = 'Per[ií]odo\s+de\s+la\s+declaraci[oó]n'`

The `modelo-369-union-extractor` application link already existed in the
revision; the profile id is wired into the construct's
`extraction_profiles` field.

Source grounding: `aeat-dr-369-2021`, `aeat-modelo-369-procedure`
(HAC/610/2021 Diseño xlsx + procedure HTML in corpus).

**PROVISIONAL LABEL PATTERNS**: The corpus artefacts are a diseño de registro (EDI
record-layout spec) and procedure HTML, NOT a real printed-declaración-form PDF
specimen. The `label_pattern` values were derived from registry casilla LABEL fields
and are unverified guesses. Verification requires a W05 round-trip parse test against
a real M369 printed-form PDF. No such PDF exists in the corpus yet.

Note: Only the Esquema Union (trimestral) revision has been profiled.
The Esquema Importacion (IOSS monthly) and Esquema Exterior revisions
have analogous structures; their profiles are deferred — no corpus PDF
fixture exists to validate against.

## Commit

`3af7ea87e` — W04: author named_label declaracion_pdf profiles for M036, M347, M369, M840
