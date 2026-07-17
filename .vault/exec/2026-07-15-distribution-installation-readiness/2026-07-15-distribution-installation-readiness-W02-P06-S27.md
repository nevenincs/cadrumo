---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S27'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S27 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Install the marketplace-served plugin in Claude and require MCP startup plus a tax-work tool call and ## Scope

- `dev/packaging/smoke_plugin_install.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Install the marketplace-served plugin in Claude and require MCP startup plus a tax-work tool call

## Scope

- `dev/packaging/smoke_plugin_install.py`

## Description

- Install the cohort-generated marketplace plugin through the real Claude Code
  configuration surface on this Windows workstation.
- Read the installed plugin declaration, launch its cohort-pinned server, and
  drive the public MCP protocol directly to the grounded tax-work oracle.

## Outcome

- The plugin-install smoke passed on 2026-07-17 against release cohort
  `616f48fcc2a748349cbfccb48952499523d3de82ad5ced1f5ec664b67024e16f` (source
  commit `044e48450e918648fd331072bda4767b47737d34`): the installed declaration
  pinned all three wheel digests, the server started via the `uvx --from`
  cohort launcher, advertised the `cadrumo_*` tool surface, and the real
  protocol calculation returned `DP200014:00562 == 23000.00` under
  `modelo-200-cuota-integra` with LIS legal references and both authoritative
  source references.
- Retained evidence document:
  `var/distribution-install-readiness/s27-plugin/run-20260717T091437Z/plugin-evidence.json`
  (schema `cadrumo.packaging.claude-plugin-evidence.v1`).

## Notes

- The optional model-driven client session half reported
  `not_run_no_credential`: no `ANTHROPIC_API_KEY` is configured locally or in
  the repository secrets. Protocol-level tax truth is the smoke's designed
  authority; the credentialed client session belongs to the S38 CI row and is
  on the operator decision list.
