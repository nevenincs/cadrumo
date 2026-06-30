---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S06'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Update the resolver enrollment catalogue for the withholding-count source

## Scope

- `src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py`

## Description

- Inspect the resolver enrollment catalogue gate.
- Run `test_source_resolver_enrollment.py` as part of the M190 proof set.

## Outcome

- `test_every_discovered_resolver_is_enrolled_or_classified` includes `aeat.application.aggregation.WithholdingSourceResolver` in `_ENROLLED_SOURCE_MESH_RESOLVERS`.
- The catalogue gate proves the exported resolver is neither dormant nor omitted from the live enrolled resolver set.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- No code change was needed for S06.
