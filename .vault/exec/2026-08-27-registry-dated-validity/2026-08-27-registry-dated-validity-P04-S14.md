---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:bfd06fc5b1dec03630ce659353c58c4e8a60cda7f29cb4a9f724cbb539e5eb0e'
step_id: 'S14'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Enrol RIRPF art. 9 and art. 22 in the legal catalogue from the already-bundled consolidated RD 439/2007, with required_text phrases read out of that file and verified present before writing, agent_reviewed provenance and an explicit operator-re-stamp note

## Scope

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `verify:` `load_registry_tree over the bundled registry` -> `pass`

## Notes

No corpus fetch was needed after all: RD 439/2007 is already bundled
consolidated, and the grounding rule prefers pointing corpus_ref at the bundled
file over hand-authoring a duplicate excerpt. Both entries are agent_reviewed
with an operator-re-stamp note, matching the sibling LIRPF entries.
