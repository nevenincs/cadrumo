---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-07-31'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:95a870964f6b87d7fd0d76ede800a3df3c13b7a22368640d9d4131e410c0c4fa'
step_id: 'S02'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Annotate ruling R3 of the agent-harness-refoundation ADR as amended by the semantic-search-precompile-boundary ADR, following the existing R2 and R8 amendment-note pattern

## Scope

- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md`

## Description

- Read the refoundation ADR and locate the existing amendment-note pattern already used on two prior rulings, so the new note matches the established placement and voice rather than inventing a style.
- Stamp ruling R3 as amended by the accepted precompile-boundary ADR, naming both the operator directive and the independent audit that established the defect class.
- Scope the amendment to the runtime embedding mechanism only: the query embedder, corpus vector build, and hybrid fusion.
- State explicitly that R3's intent carries over unchanged, and that the future laundered precompiled artefact is an open pathway rather than a commitment.
- Preserve the original ruling text below the note for the decision trail.

## Outcome

The note is in place at the head of R3 and is accurate on the point that matters most for a future reader: it records that this is an amendment with a stated reason rather than a reversal or a discovered inconsistency, noting that R3 was a deliberate decision made behind a licence gate later satisfied, predating the operator clarification, and that only its implementation broke its own reproducibility and storage-root promises. The original ruling text survives intact beneath the annotation. Vault checks introduced no new errors.

## Notes

The precision here was deliberate. An earlier framing in coordination treated the whole runtime stack as architectural drift; that is accurate only for the corpus-vector half, which the founding research specified as precompiled-and-shipped and which no build step ever wired. The runtime query embedder was chosen deliberately. Recording the distinction prevents a later reader from concluding the original ruling was careless, and prevents the amendment from being read as licence to revisit the parts of R3 that still stand.
