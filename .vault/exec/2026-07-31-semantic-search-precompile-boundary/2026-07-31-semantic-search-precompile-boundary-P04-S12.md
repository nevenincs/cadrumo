---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:90349214fbfa22465a6e46c739ae3be81c396a00bc532fbac0ca661af40e99d0'
step_id: 'S12'
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
     The S12 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Sweep the operator harness documents and user documentation for hybrid or semantic retrieval claims and verify the docs build gates and ## Scope

- `docs/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep the operator harness documents and user documentation for hybrid or semantic retrieval claims and verify the docs build gates

## Scope

- `docs/`

## Description

- Ground by MEANING first: a `vaultspec-rag` code search scoped to the docs domain for user-facing prose explaining how corpus grounding finds legal text by concept or meaning.
- Sweep the operator harness tree `src/cadrumo/_data/agent/` for hybrid, semantic, embedding, model2vec, and retired-extra claims.
- Sweep user documentation and the README for the same vocabulary plus vector search, concept recall, and the retired extra.
- Sweep the packaging manifests for the same claims.
- Verify the docs build gates: the generated-stub drift check and the stub health audit.

## Outcome

Step satisfied with no edits required; both surfaces were already truthful at HEAD and this record states the evidence rather than asserting a sweep happened.

Operator harness tree: `rg -i` over `src/cadrumo/_data/agent/` for hybrid, semantic, embedding, model2vec, and `[search]` returns ZERO matches. The harness is clean.

User documentation: `rg -i` over `docs/` (md, rst, txt) and `README.md` for semantic, hybrid, embedding, model2vec, huggingface, `[search]`, vector search, and concept recall returns no stale retrieval claim. Every hit is an unrelated homonym and was deliberately left alone: the registry's `_semantic_role_*` validators and their generated API stubs (semantic ROLE, a registry concept), "usage-ratio semantics" in the bank-statement how-to, and "tax semantics" in the API index. Packaging manifests return zero matches.

Docs build gates: `python -m dev.docs.apidocs scaffold --check` reports "Stub tree is conformant. No drift detected."; `python -m dev.docs.apidocs audit` reports 1246 source modules, 1246 stub files, 0 missing, 0 orphan, 0 stale.

## Notes

The prior read-only inventory's claim that the harness tree and `docs/` were clean is CONFIRMED at current HEAD by independent re-measurement, not inherited. No work was invented to justify the row.

Scope discipline observed: `dev/docs/` and `dev/deploy/` were NOT touched (a peer agent holds uncommitted and untracked work there). This is correct on the merits as well as for safety - `dev/docs/terminology/` legitimately describes embedding and hybrid retrieval because it IS the dev-side precompile oracle that ADR ruling R2 depends on. Those are true statements about the dev pipeline, not stale product claims, and must not be swept.

The apidocs check measures a working tree that also carries a peer agent's untracked stub files; it reports zero orphans and zero missing, so the result is clean for this step's scope either way.
