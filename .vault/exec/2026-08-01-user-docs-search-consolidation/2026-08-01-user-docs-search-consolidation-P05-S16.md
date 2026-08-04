---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7512550deb09c2476de831fff935fda07d7dfeb783c9296ebdd37a794abab162'
step_id: 'S16'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-search-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-08-01-user-docs-search-consolidation-plan placeholders are machine-filled by
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
     The Reconcile the committed legal relevance targets to the new record ids and extend the target-resolution gate to refuse any target id no injector emits and ## Scope

- `src/cadrumo/_data/terminology/relevance/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reconcile the committed legal relevance targets to the new record ids and extend the target-resolution gate to refuse any target id no injector emits

## Scope

- `src/cadrumo/_data/terminology/relevance/`

## Description

- Reconcile each existing `legal:` relevance target against the generated legal-reference renderer, preserving mapping order, record ids, surfaces, and ranking weights while setting the kind to `legal`.
- Extend the real target-resolvability gate with the injector-backed legal record-id-to-target inventory, rejecting missing ids, mismatched generated targets, non-LEGAL kinds, and direct BOE search targets while retaining non-legal drift and anti-tautology checks.
- Update the recorded prorrata sweep assertions to require exact generated legal destinations and independently verify BOE provenance on resolved search records.
- Run only JSON parsing, AST parsing, exact `rg` checks, `git diff --check`, and conflict-marker scanning.

## Outcome

Implemented the S16 relevance reconciliation and fail-closed legal target gate. The committed artifact retains all 112 mappings and 726 target slots; 338 legal slots now use renderer-generated destinations with `kind: legal`, including the page-level `_generated/legal/boe-a-2023-24840.html` target.

## Notes

- The current legal projection emits provision ids, not the two legacy `legal:rd-1007-2023` ids; the gate intentionally reports those missing ids as unresolved until the registry/relevance authority is reconciled. No alias or new mapping was invented.
- `dev.docs.terminology._legal_projection` cannot be imported in this dirty tree because of a pre-existing `_miss_rate`/`_legal_projection` circular import; the artifact targets were derived directly from the same `dev.docs.legal_reference` renderer authority without modifying that unrelated surface.
- Per instruction, no tests, builds, Pagefind runs, live probes, sweeps, deployment, or reindexing were run.
