---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget dynamic imports to public Cadrumo facades and ## Scope

- `src/cadrumo dynamic import sites` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget dynamic imports to public Cadrumo facades

## Scope

- `src/cadrumo dynamic import sites`

## Description

- Ground dynamic import and public facade rules against representative production epicenters.
- Retarget qualified product module references and importlib targets without changing authority identifiers.
- Exclude tests, eval tests, persistence namespaces, cryptographic contexts, settings, and S14 error registries.
- Verify syntax, focused lint, formatting, residue, plan state, and import smoke.

## Outcome

Retargeted 86 product-qualified module references across 16 production Python files. The changed set covers three literal `importlib` targets, payload package discovery, registry cross-domain checks, public-facade examples, service-owner metadata, logger/module identifiers, and qualified annotations. `adapters.outbound.aeat`, `registry/aeat`, AEAT URLs/prose, persisted namespaces, retained settings, and error registry declarations remain unchanged.

## Notes

- A first candidate rewrite was deliberately rolled back from non-module strings after review; the final diff contains only the 16 classified module-reference files.
- All 16 files passed compileall, Ruff `E9/F63/F7/F82`, and format checks. The uv-environment import smoke reaches `cadrumo.core` and then stops at the expected S14 error-registry mismatch for `cadrumo.core.errors.CoreError`; error registry reconciliation was not pulled forward.
