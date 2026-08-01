---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-07-31'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:39d956c0ae5539709ed48cab16834b65eb18d19ee553f88fd3539182062e8e49'
step_id: 'S02'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Annotate ruling R3 of the agent-harness-refoundation ADR as amended by the semantic-search-precompile-boundary ADR, following the existing R2 and R8 amendment-note pattern and ## Scope

- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
