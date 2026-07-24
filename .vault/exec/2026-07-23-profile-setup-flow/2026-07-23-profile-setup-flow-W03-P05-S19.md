---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S19'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Render the legal-provenance zone from schema legal_refs plus the reverse index with approved-concept references only

## Scope

- `src/cadrumo/application/wizard/`

## Description

- `build_flow_legal_zones` projects, per profile-bound page, the union
  of the schema field's `legal_refs` and the registry reverse index's
  entry (consuming modelos + binding refs) into a typed page-keyed
  mapping; pages absent from both sources are omitted.
- Approved-only terminology references resolve through the
  `profile-terminology:` namespace resolver over the production
  corpus-search loader; the schema descriptions through
  `profile-schema:`.
- The render half landed on the substrate side (the legal-reference
  line on the page surface), giving the projection a live consumer:
  registry-derived grounding reaches the operator's screen end to end.

## Outcome

Landed across the copy/grounding cluster commit and the substrate's
rendering landings; verified live (the censo-status grounding chain and
the 21 binding-derived catalogue pages render their citations).
Receipt: the legal-zone tests (4) plus the copy-source tests (8) green.

## Notes

Content coverage beyond the reverse index's reach (pages grounded only
by schema refs) is data-complete; any page carrying neither source
correctly renders no legal zone. Approved-concept gating means a future
page citing an unapproved concept fails loudly at render, per design.
