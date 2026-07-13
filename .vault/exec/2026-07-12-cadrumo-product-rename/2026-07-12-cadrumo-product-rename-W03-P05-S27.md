---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S27'
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
     The S27 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update the optional-extra authority and every directly generated runtime install remedy to current `cadrumo[...]` metadata, with real degradation tests and ## Scope

- `src/cadrumo/core/_optional_extras.py`
- `optional-extra consumers`
- `error registries`
- `agent/MCP/search/corpus degradation surfaces and direct tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the optional-extra authority and every directly generated runtime install remedy to current `cadrumo[...]` metadata, with real degradation tests

## Scope

- `src/cadrumo/core/_optional_extras.py`
- `optional-extra consumers`
- `error registries`
- `agent/MCP/search/corpus degradation surfaces and direct tests`

## Description

- Point the optional-extra authority at `cadrumo[extra]` installation commands.
- Converge directly emitted Google, browser, Anthropic, agent, search, and corpus-source remedies on current metadata.
- Update real degradation and error-envelope assertions without introducing test doubles.
- Preserve third-party import names and AEAT authority, Sede, evidence, and registry semantics.

## Outcome

Every active Python runtime remedy uses the Cadrumo distribution and a declared
extra. The real lean-core, missing dependency, search, corpus companion, and MCP
refusal tests pass together: 19 passed.

## Notes

The existing meta-path import blocker remains the real import-isolation mechanism;
this step introduced no mocks, patches, monkeypatches, skips, or expected failures.
Historical rule names and AEAT authority identifiers were not renamed.
