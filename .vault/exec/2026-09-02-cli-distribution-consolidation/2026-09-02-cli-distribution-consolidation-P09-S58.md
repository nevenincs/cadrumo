---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c8cb16994ab68b0ecb69243910635e5dd7a2a02371f3168f39cd69af4f721f1b'
step_id: 'S58'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Keep a corpus annotation in the same distribution as the file it annotates

## Scope

- `pyproject.toml`

## Changes

- `M` `src/cadrumo/core/resources/bundled_data.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_sources.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_record_design_annotation_survives_the_data_split.py`
- `M` `src/cadrumo/core/resources/tests/test_corpus_companion_seam.py`

## Notes

The defect reached three times as far as the failing gate showed. Ten annotated
record designs diverged under an installed split, not two, because only two of
them are reached by the validating load at all. One modelo reported itself
COMPLETE across both revisions while silently not applying two declared
corrections, which is worse than the incomplete reading that raised the alarm:
wrong values, nothing missing, nothing said. Another raised outright.

Nothing moved between distributions. The companions' partition contract already
states that only binary suffixes travel and derived surfaces stay, and one
annotation family cannot be colocated at all -- its extracted text must remain
in the root wheel for grounding search while its binaries ship in a companion.
Colocation was therefore never available as an invariant, only as a
coincidence that each new annotation family would have to re-earn in two
exclude lists and a build hook.

The resolution seam already existed and was documented as canonical; the
annotation loader was the one caller that had escaped it with a raw sibling
lookup. Two divergent copies across roots is now a refusal naming both, since
spanning roots to find an annotation means a mis-partitioned cohort could offer
two and installation order would otherwise decide a grounding question.

Two correction sidecars annotate a binary that exists in neither the source
tree nor any companion. They duplicate a live sibling whose own recorded reason
says the two containers carry one defect between them. They are dead
declarations, and removing corpus data is a grounding act rather than a
packaging one, so they are reported and left.

## Scope

- `pyproject.toml`

## Changes
