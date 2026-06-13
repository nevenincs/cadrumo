---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S87
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W05.P15.S87 - correct modelo-115 calc-verify ADR extractor-class prose

## Outcome

`.vault/adr/2026-04-27-modelo-115-calc-verify-adr.md` corrected.

Two stale passages described the deleted per-modelo extractor-class mechanism as
implemented:

- **D2** described adding `Modelo115V2024Extractor` / `Modelo115V2026Extractor`
  sibling subclasses and registering them in `_extractors/__init__.py`.
- **Negative consequences** described the `_REGISTERED_CLASSES` tuple widening.

A dated correction note (2026-05-21) was appended after each stale passage
clarifying that the `DeclaracionExtractor` ABC, `GenericDeclaracionExtractor`,
the `_extractors/` registry, and all per-modelo extractor subclasses were deleted;
declaración extraction is now driven by registry `declaracion_pdf` extraction
profiles. Reference to `2026-05-21-declaracion-extraction-architecture-adr`
added.

The historical decision text was preserved intact; only correction notes were
added.
