---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:3dd27983aa920b0c4fbd1d75b7190c7133a71502b68645b9e57ccf3abc8f1b14'
step_id: 'S11'
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
     The S11 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Sweep the MCP corpus and meta tool descriptions and docstrings to describe lexical plus citation retrieval, keeping the harness rule-surface drift gate green and ## Scope

- `src/cadrumo/entrypoints/mcp/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep the MCP corpus and meta tool descriptions and docstrings to describe lexical plus citation retrieval, keeping the harness rule-surface drift gate green

## Scope

- `src/cadrumo/entrypoints/mcp/`

## Description

- Ground the sweep by MEANING first, per the operator's mandatory-discovery directive: two `vaultspec-rag` code searches (the MCP corpus tool description surface, and embedding/vector/fusion ranking) before any keyword pass.
- Confirm the exact sites with a targeted `rg` over `src/cadrumo/entrypoints/mcp/` for the full stale-claim vocabulary (semantic, embedding, embedder, hybrid, model2vec, potion, huggingface, vector, RRF, reciprocal rank).
- Read every model-facing description at HEAD rather than trusting the prior read-only inventory: the `cadrumo_corpus_search` tool description and its module docstring, the `cadrumo_terminology_search` docstring, and all four meta-tool descriptions built by `build_meta_sdk_tools`.
- Correct the one genuinely stale claim found: the comment above the command-index construction still called the index "hybrid".
- Re-run the harness rule-surface drift gate.

## Outcome

Step satisfied. The sweep found the model-facing surface already truthful and one stale internal comment, which was corrected.

Already correct at HEAD, confirmed by direct read (not inherited from the earlier inventory): the `cadrumo_corpus_search` tool description reads "Search the bundled BOE/AEAT legal corpus and terminology for grounding. Returns ranked hits with a verbatim snippet and a `cadrumo://corpus/{ref}` URI resolving the full authoritative text; an exact citation id resolves directly" - no semantic claim; its module docstring already states "The search is fully offline: no model, no vectors"; the `search` meta-tool reads "Search Cadrumo commands by keyword"; the `execute`, `toolsets`, and `describe` descriptions carry no retrieval claim at all; and the `search` meta-tool's ranking docstring already describes "the lexical command index (per-column FTS5 BM25 + Spanish stemming + diacritics folding, degrading to token overlap)".

One real correction landed: in `src/cadrumo/entrypoints/mcp/_server.py`, the comment above the command-index construction read "The hybrid command-search index backing the `search` meta-tool" and now reads "The lexical command-search index". This is a decision-trail claim a maintainer would have taken as current architecture; it survived the P02 rewire because the rewire touched the index implementation, not the server's construction-site comment.

One near-miss deliberately NOT changed: `_tools.py` describes the input schema as "the CLI argument vector". That is the ordinary sense of vector (an argument list), not an embedding claim, so editing it would have been fabricated work.

Gate: the harness rule-surface drift gate `src/cadrumo/agent/tests/test_rule_surface_conformance.py` run serially with the marker override reports `6 passed in 4.81s`.

## Notes

The earlier read-only inventory's conclusion that the four model-facing tool descriptions were already clean is CONFIRMED at HEAD, but it was incomplete: it did not cover the `_server.py` construction-site comment, which was stale. Re-measuring rather than trusting the inherited finding is what surfaced it. No skipped work, no scaffolds left in code.
