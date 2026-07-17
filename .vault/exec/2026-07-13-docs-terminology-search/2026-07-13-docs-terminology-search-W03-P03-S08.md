---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet

## Scope

- `src/cadrumo/_data/terminology/`

## Description

- Curate and promote 20 skill-backed modelo draft concepts to approved:
  036, 111, 115, 123, 131, 180, 184, 190, 193, 200, 202, 210, 232, 309,
  322, 347, 349, 353, 369, 720 (commit `76262fda26`).
- Ground every concept: registry-validated legal_refs, related edges into
  the approved graph, curated Spanish definition with BOE citation and
  preferred/admitted terms, en/ca/hu short descriptions.
- Absorb the glossary generator's src/aeat legal-catalogue path (rename
  straggler that zeroed every legal grounding link).

## Outcome

Approved tier 29 -> 49 concepts; handbook loader clean; all 17 glossary
gates green with 555 permalinked groundings restored. The synonym
ratification ratchet untouched (no candidate bypassed review).

## Notes
