---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W03.P06.S20'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# W03.P06.S20 - Modelo 180 declaracion_pdf profile blocked

Blocked under the legal-and-verified execution rule.

## Grounding

Modelo 180 has current registry/source grounding for the submitted-file
surface:

- `revision.toml` cites `aeat-dr-180-2023`,
  `aeat-modelo-180-procedure`, `aeat-modelo-180-ayuda-presentacion`,
  `boe-modelo-180-2014-form`, and `boe-modelo-180-2023-form`.
- `extraction_profiles/0001-modelo-180-export-record.toml` defines the
  existing `export_record` profile against the submitted-file parser.
- The declaration summary casillas `decl.total-perceptores`,
  `decl.base-total`, and `decl.retenciones-total` are present with
  legal/source refs.

That evidence is sufficient for submitted-file extraction. It is not
enough to author a `declaracion_pdf` profile, because the current corpus
does not contain an authorised Modelo 180 declaration PDF fixture or a
printed declaration layout to prove the visible labels and values that
the generic PDF parser would match.

## Disposition

Leave `W03.P06.S20` open and blocked by `W05.P11.S92`. Do not infer a
PDF profile from export-record labels alone. Re-open only after an
authorised Modelo 180 declaration PDF fixture or official printed-form
layout is added and can be exercised by a real parser test.
