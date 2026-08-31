---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c229361d3b4ec4a2c6ed3a6e7473c585d53825a1b6e615c6fe9454f4c2695c51'
step_id: 'S110'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on which CIF leader-class policy is authoritative, after grounding it against the official norm, and collapse the two identity validators that currently answer the same input differently

## Scope

- `src/cadrumo/core/identity/`

## Changes

- `verify:` one `_validate_cif` remains in the identity package, in `_documents.py`
- `verify:` recorded in `.vault/audit/2026-08-30-semantic-consolidation-cif-leader-policy-audit.md`

## Notes

Closed by S131. The operator ruled that two validators answering one question
differently is the defect rather than the question, and the direction was not a
free choice: AEAT partitions the CIF kind letters three ways, `_documents`
already implemented that partition, and `_tax_id`'s own module docstring stated
it correctly while the code beneath it accepted the letter form for `ABEH`.

The four restated validators in `_tax_id` are gone, 140 lines, and the surviving
one kept the richer refusal payload rather than the poorer. A structural gate now
holds each policy table and the checksum arithmetic to one declaration.
