---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S66'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace agent-harness-refoundation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S66 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Add the regularizar-atrasos golden scenario and ## Scope

- `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the regularizar-atrasos golden scenario

## Scope

- `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`

## Description

- Read the eval runner contract in full before authoring: trajectory keys must
  resolve via `command_schema_refs()`, lifecycle order binds only the
  modelo.work stages present, and every trajectory verb's CLI form must appear
  verbatim in the owning skill's text.
- Probe the registry: 303/2024/1T resolves with a grounded verification
  contract carrying casillas 64/66; all five overview keys plus
  `modelo.work.amend` resolve as command keys.
- Author `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`: trajectory
  is the situation skill's own driven surface (`overview.status`,
  `overview.backlog`, `overview.explain`); the delegated catch-up spine stays
  covered by the per-modelo scenarios.

## Outcome

Scenario authored by the coordinator; the all-scenario sweep
(`test_modelo_130_golden.py`, 9 passed) includes and passes it. Commit
`229127db6`, exactly one file.

## Notes

The wider eval lane showed ~26 concurrent failures at authoring time
(replay/under-declaration/exit-code tests) consistent with the W01 executor's
in-flight edits to the MCP dispatch surface — signature reported to that
executor, whose wave gate was extended to the full
`src/aeat/entrypoints/mcp src/aeat/agent` lane. Not absorbed here: this
Step's sweep is green in isolation.
