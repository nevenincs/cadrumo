---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S86
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P08.S86 - M037 fetch-versus-defer decision

## Outcome: DEFER — source-blocked

Inspected `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_037/manifest.json`.

The manifest confirms zero artefacts and records:

> "No matching official AEAT disenos-registro link was found for this supported
> corpus modelo on the current or previous official index pages."

There are no instructions in the `instructions/` corpus directory (no `modelo_037`
sub-directory exists). No Diseño PDF, no Orden ministerial, no form specimen.

Decision: DEFER. M037 is a simplified census form (simplified version of M036 for
natural-person freelancers) but AEAT does not publish a Diseño de Registro for it,
and no instructions PDF or HTML is in the corpus. Authoring a `named_label`
extraction profile without a printed-form specimen would require fabricating
`label_pattern` values with no official grounding — forbidden by the ADR and
project rules.

M037 has no registry presence (`src/aeat/_data/registry/aeat/modelos/` contains
no `037*` entry). W04.P09.S27 (register M037) and W04.P10.S29 (author M037 profile)
remain open pending a corpus fetch task.

## Action

No code changes. This Step is a decision record only.
