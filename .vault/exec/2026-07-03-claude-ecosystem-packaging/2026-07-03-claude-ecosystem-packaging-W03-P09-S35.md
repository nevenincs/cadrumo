---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S35'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S35 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Test the requiresUserInteraction annotation is present on every CONFIRM-tier tool and absent on read-only tools and ## Scope

- `src/aeat/entrypoints/mcp/tests/test_annotations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test the requiresUserInteraction annotation is present on every CONFIRM-tier tool and absent on read-only tools

## Scope

- `src/aeat/entrypoints/mcp/tests/test_annotations.py`

## Description

- Add proof to `test_annotations.py` that `_meta["anthropic/requiresUserInteraction"]` is present on exactly the `CONFIRM`-tier tool set built by `build_sdk_tools`.
- Assert every read-only tool carries no `_meta` entry for the flag.
- Assert the derivation is automatic for a new `CONFIRM`-tier tool (no hand-listed-tool regression), exercising the real `confirmation_for_tool` classification rather than a stubbed policy.
- Commit `118ff006d0`.

## Outcome

- `pytest src/aeat/entrypoints/mcp/tests -m integration`: 138 passed (2 new).
- `ruff check` clean.

## Notes

No incidents. No skipped work.
