---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S25
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P09.S25 - M720 dead-stub verification

## Outcome: Already correct — no action needed

Inspected `src/aeat/_data/registry/aeat/modelos/720.toml`.

The `modelo-720-declaracion-pdf` extraction profile exists in
`revisions."2013-y-siguientes"` with two `named_label` targets:

- `decl.ejercicio` — `named_label`, `value_kind=amount`
- `decl.tipo-declaracion` — `named_label`, `value_kind=enum`

The profile was authored as part of the W02 work. No dead stub exists;
the profile loads and validates clean. The construct references
`extraction_profiles = ["modelo-720-declaracion-pdf"]` and the
`modelo-720-extractor` application link is wired.

## Action

No code changes required.
