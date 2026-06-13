---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S27
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P09.S27 - M037 registry registration

## Outcome: SOURCE-BLOCKED — deferred

M037 has no registry presence (no `037*` file in
`src/aeat/_data/registry/aeat/modelos/`).

The corpus manifest for M037 (`disenos_registro/modelo_037/manifest.json`)
confirms zero artefacts (`artefact_count: 0`) with the note:

> "No matching official AEAT disenos-registro link was found for this
> supported corpus modelo on the current or previous official index pages."

No instructions directory exists for M037 in the `instructions/` corpus.

Registering M037 without a printed-form specimen to ground the casilla
labels, `label_pattern` values, and legal_refs would require fabrication
against ADR and project rules.

This Step is blocked pending a corpus fetch. A follow-up task should
fetch the M037 Orden ministerial (RD 1065/2007, Orden EHA/1274/2007 for
the simplified census form) and add it to the corpus before proceeding.

## Action

No code changes. Step left open.
