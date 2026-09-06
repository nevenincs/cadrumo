---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:18ef188b5d80171464eed3b520ea1c79086a4a8030e11ce93a5369a7a0ba4ee8'
step_id: 'S46'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate the grounding-anchor provenance wrappers and the invoice CLI query projections, and record what the first is NOT: the anti-fabrication contract's structural half is live, since evaluate anchor, the printed-excerpt predicates, the refusal constructor and the ambiguous-candidate grounder are all imported by production modules, so an extracted value is still checked against the transcription and only the envelope-building convenience is displaced by callers constructing the provenance directly; the two invoice projections declare themselves for CLI surfaces that never reach them, while a sibling in the same module is consumed

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

`grounding_anchor` is the clearest case yet for classifying symbols rather than
modules. Read as a file it looks like the anti-fabrication check going unrun,
which would be a serious finding for LLM-extracted values. Five of its symbols
are imported by live production modules, so the check runs; the two findings are
provenance-envelope wrappers whose callers build the envelope themselves.
