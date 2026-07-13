---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S08'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-protocol-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-08-mcp-protocol-hardening-plan placeholders are machine-filled by
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
     The Extend the descriptor tests for real defaults, off-token round-trips, and the loud-degradation gate and ## Scope

- `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the descriptor tests for real defaults, off-token round-trips, and the loud-degradation gate

## Scope

- `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`

## Description

- Implemented as part of the P02 (input-schema fidelity) phase; the executed action is the plan step named in the heading above.

## Outcome

- Executed and merged in commit `5c591e7734` (feat(mcp): classification table, toolset activation, input-schema fidelity, boundaries, retention). Green in the current mcp suite (241 passed) at reconciliation time.

## Notes

- Exec record backfilled by reference on 2026-07-10 during the P04 result-thinning reconciliation: this step was executed and landed by the commit(s) above before per-step exec records were authored for phases P01-P03 / P05-P06. The backfill changed no code; it records the existing landing so the plan closes with execution evidence per the plan-closure-requires-exec-records discipline.
