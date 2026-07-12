---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S25'
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
     The S25 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Project `cadrumo` as the sole human executable across runtime identity, version/help authorities, command paths, diagnostics, and real CLI structural tests and ## Scope

- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/application diagnostics/operator surface and product-owned command guidance`
- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/tests/cli_runner.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Project `cadrumo` as the sole human executable across runtime identity, version/help authorities, command paths, diagnostics, and real CLI structural tests

## Scope

- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/application diagnostics/operator surface and product-owned command guidance`
- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/tests/cli_runner.py`

## Description

- Set `cadrumo` as the sole console script, runtime executable identity, Typer root name, and pinned program name.
- Rename product-owned command paths, subprocess arguments, completion context, diagnostics, examples, and structural-test authorities.
- Preserve AEAT names for the authority adapter, Sede behavior, official evidence, legal semantics, registry taxonomy, and protocol fields.
- Prove the real executable, root/help/version surfaces, command-row resolution, state-independent help, and absence of an installed `aeat` executable.

## Outcome

The installed Cadrumo distribution exposes `cadrumo` and no `aeat` executable.
The short version surface reports `cadrumo 0.1.1`; authored root, config, and app
command rows use `cadrumo`; and nine focused real-behavior tests pass. Scoped
Ruff formatting and lint checks pass across the renamed command authorities.

## Notes

The Spanish locale still contains one translated sentence spelling
`aeat <comando> --help`. Locale catalogues were deliberately not edited in this
step; their CLI-owned regeneration remains assigned to S62-S67. A concurrent
edit briefly restored the superseded executable spelling while verification was
running; S25 reasserted the requested single Cadrumo command before commit. No
data was deleted or migrated.
