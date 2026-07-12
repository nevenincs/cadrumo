---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S34'
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
     The S34 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget runtime companion discovery exclusively to the `cadrumo_data` PEP 420 namespace and prove byte access across both built wheel portions and ## Scope

- `src/cadrumo/core/resources/_boundary.py`
- `src/cadrumo/core/resources/tests/test_corpus_companion_seam.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget runtime companion discovery exclusively to the `cadrumo_data` PEP 420 namespace and prove byte access across both built wheel portions

## Scope

- `src/cadrumo/core/resources/_boundary.py`
- `src/cadrumo/core/resources/tests/test_corpus_companion_seam.py`

## Description

- Derive companion discovery from the canonical Cadrumo identity tuple.
- Remove the former namespace from resource-boundary prose, constants, fixtures, and module cleanup.
- Preserve `aeat_official` as the official authority corpus partition.
- Build both real companion wheels and read byte-exact payloads through the production resource resolver.

## Outcome

Runtime discovery now calls `importlib.resources.files` for `cadrumo_data` only,
with no former namespace fallback, alias, or dual import. Both synthetic
multi-portion coverage and freshly built manuals/official wheel portions resolve
through the same production boundary. Nine focused degradation, discovery,
byte-access, and missing-companion tests pass.

## Notes

The official wheel continues to use `corpus/aeat_official`, which identifies
official AEAT source evidence and is not a product namespace. Existing unrelated
staged core changes are excluded from S34 through an explicit four-path commit.
