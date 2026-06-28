---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S88
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W05.P15.S88 - correct modelo-303 calc-verify ADR extractor-class prose

## Outcome

`.vault/adr/2026-04-27-modelo-303-calc-verify-adr.md` corrected.

The Implementation section described `Modelo303V2026Extractor` as a thin subclass
of `Modelo303V2025Extractor` pinning only `TemplateRevision`. A dated correction
note (2026-05-21) was appended immediately after that sentence clarifying that the
`DeclaracionExtractor` ABC, `GenericDeclaracionExtractor`, the `_extractors/`
registry, and the `Modelo303V2026Extractor` class were subsequently deleted;
declaración extraction is now driven by registry `declaracion_pdf` extraction
profiles. Reference to `2026-05-21-declaracion-extraction-architecture-adr` added.

The historical decision text was preserved intact; only a correction note was
appended.
