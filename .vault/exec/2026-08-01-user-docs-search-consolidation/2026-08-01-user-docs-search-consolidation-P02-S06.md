---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c19df98575a6134e927a2663c4a21e1b9515cf3b2227a74fc7b29747bbf6100c'
step_id: 'S06'
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
     The S06 and 2026-08-01-user-docs-search-consolidation-plan placeholders are machine-filled by
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
     The Extend the licence gate to validate the shipped matrix's provenance stamp, model licence, and size bound while keeping every oracle-output and NC-ND bar intact and ## Scope

- `dev/docs/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the licence gate to validate the shipped matrix's provenance stamp, model licence, and size bound while keeping every oracle-output and NC-ND bar intact

## Scope

- `dev/docs/tests/`

## Description

## Description

- Re-ground P02.S06 with current vaultspec-rag searches over the Rung-2 acceptance, bundle, matrix, provider, and content-manifest source seams, plus the accepted consolidation ADR updates.
- Inspect the current source-only contract without running tests, builds, model downloads, artifact generation, runtime probes, live sweeps, reindexing, or deployment.
- Record whether the licence/provenance/size gate is absent, incomplete, or present but evidence-gated.

## Outcome

## Outcome

The source-side P02.S06 contract is present. The acceptance boundary validates canonical bundle bytes and SHA-256 identity, the shared serialized-byte bound, embedded input-provenance fingerprints, and the ratified model repository, immutable revision, SPDX licence, and dimension. The matrix schema restricts the accepted licence set, while the provider requires raw-byte manifests for provider, model, and tokenizer roles before importing the optional provider or loading model content.

No shipped matrix, real provider/package/model/tokenizer manifests, measured quantization evidence, or held-out acceptance evidence is present. P02.S06 therefore remains unchecked: this record establishes source readiness, not licence-gate or artifact acceptance.

## Notes

## Notes

- No tests, builds, model downloads, generated artifacts, Pagefind/runtime probes, live sweeps, RAG reindexing, or deployment were run.
- No source file was changed in this tranche; concurrent shared-worktree changes were preserved.
- Closure requires real manifest and provider evidence plus the authorized acceptance gates; the standing no-tests boundary remains in force.
