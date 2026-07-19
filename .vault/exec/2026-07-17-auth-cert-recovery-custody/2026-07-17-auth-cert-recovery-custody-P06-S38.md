---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S38'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs and ## Scope

- `src/cadrumo/agent/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-arm the MCP mirror for the accepted auth, certificate, and recovery verbs

## Scope

- `src/cadrumo/agent/`

## Description

- Re-arm the MCP mirror for the recovery family: the mirror derives its verbs from the risk table and the registered payload schemas, so the new `config.recovery.*` rows and schemas (and the removal of the retired ids) propagate it.
- Verify with the MCP suite including the per-verb CLI-vs-MCP schema-parity diff and gate-refusal tests.

## Outcome

MCP suite green (301 tests) over the accepted auth, certificate, and recovery verbs.

## Notes

No hand-authored MCP verb list exists for these families; the risk-table plus schema registry is the single mirror source.
