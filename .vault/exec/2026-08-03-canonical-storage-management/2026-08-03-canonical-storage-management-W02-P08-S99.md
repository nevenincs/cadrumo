---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5bf8bac896a8937c173dfa1cbd6e9ed8d204617ceea028bcd09b60f1fbb51f47'
step_id: 'S99'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S99 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Add one parameterised helper collapsing the five copy-pasted optional-root Typer resolvers, covering both the bundled-default family in registry.py and the settings-default family in registry.py and _app_live.py, so the two families stop drifting apart independently and ## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add one parameterised helper collapsing the five copy-pasted optional-root Typer resolvers, covering both the bundled-default family in registry.py and the settings-default family in registry.py and _app_live.py, so the two families stop drifting apart independently

## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `d9145d3b83`, confirmed at HEAD. `resolve_optional_root(value: Path | None, default: Callable[[], Path]) -> Path` in `src/cadrumo/entrypoints/cli/_common.py:562` is the single parameterised helper, taking the default as a lazily-invoked callable so it computes only when the operator supplies no override (unchanged behaviour). Covers both the bundled-default family (registry/workbook/source roots) and the settings-default family (parity store root, live output roots).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
