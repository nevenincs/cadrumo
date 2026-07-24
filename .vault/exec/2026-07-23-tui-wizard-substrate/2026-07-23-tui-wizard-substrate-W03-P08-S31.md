---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S31'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Migrate the amend wizard consumer onto the engine frontends, removing its local one-shot prompt helper and ## Scope

- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the amend wizard consumer onto the engine frontends, removing its local one-shot prompt helper

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Rebuild the amend wizard as a flow definition on the shared substrate (per-run copy table under the `modelo-amend` namespace, two-round flow) and drive it through the capability-selected frontends.
- Remove the module-local one-shot prompt helper the amend path had re-homed during the earlier consumer break-fix.
- Keep the non-interactive branch on the scripted intent driver so both transports share one flow authority.

## Outcome

Landed at commit `ab1d352f61`. The amend wizard walks the same engine, frontends, and validation as the setup flow; no local prompt implementation remains in the module. Its conformance and CLI tests are green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- This step completed the consumer sweep that unblocked the atomic retirement in `S26`.
