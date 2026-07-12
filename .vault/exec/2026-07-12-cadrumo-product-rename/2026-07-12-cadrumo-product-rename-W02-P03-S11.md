---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S11'
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
     The S11 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget packaged-resource lookup to the Cadrumo root and ## Scope

- `src/cadrumo/core/resources` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget packaged-resource lookup to the Cadrumo root

## Scope

- `src/cadrumo/core/resources`

## Description

- Ground the packaged-data boundary semantically and read its implementation in full.
- Retarget the primary package anchor through the canonical Cadrumo identity.
- Preserve the authority-owned `registry/aeat` taxonomy and defer the companion namespace to S34.
- Run direct real-resource, lint, formatting, residue, plan, and diff checks.

## Outcome

`files()` now consumes `PRODUCT_IDENTITY.python_package`, resolving `cadrumo/_data` without duplicating the product string authority. Resource facade and boundary prose identify Cadrumo, while `aeat_data`, `aeat_official`, and `registry/aeat` remain unchanged because they are companion/authority surfaces outside this Step.

## Notes

- No mocks, patches, new tests, dynamic-string rewrites, or authority taxonomy changes were introduced.
- The first focused pytest invocation was blocked before collection by the repository-root `conftest.py` still importing the removed `aeat` package; this is pre-existing post-relocation debt outside the resource boundary. The broad resource-directory Ruff invocation also surfaced 22 pre-existing test-docstring findings, so lint verification was narrowed to the two edited production files.
