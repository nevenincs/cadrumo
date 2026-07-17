---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S25'
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
     The S25 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Generate plugin bootstrap configuration that resolves the complete cohort and ## Scope

- `src/cadrumo/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Generate plugin bootstrap configuration that resolves the complete cohort

## Scope

- `src/cadrumo/agent/_workspace.py`

## Description

- Verify the plugin bootstrap generator resolves the complete three-wheel cohort.
- Confirm `_materialise_plugin_python_cohort` embeds the root, manuals, and
  official wheels with their SHA-256 digests and emits the
  `plugin-python-cohort.json` manifest consumed by the launcher arguments.
- Confirm the generated MCP configuration launches the embedded cohort through
  `uvx --from` with all three wheels pinned, never an ambient installation.
- Exercise the generator through the real plugin materialisation path used by
  the marketplace tree and the live plugin-install smoke.

## Outcome

- The bootstrap implementation shipped in `src/cadrumo/agent/_workspace.py`
  (cohort model, wheel map, launcher argument builder, cohort materialiser) and
  was proven twice on 2026-07-17: the marketplace generation gate passed 4/4,
  and the live plugin-install smoke installed the generated plugin through the
  real Claude Code configuration and completed the grounded Modelo 200 oracle
  (`DP200014:00562 == 23000.00` under `modelo-200-cuota-integra`) against the
  release cohort at source commit `044e48450e918648fd331072bda4767b47737d34`
  with all three wheel digests pinned in the installed declaration.
- Retained evidence: the release cohort manifest (cohort id
  `616f48fcc2a748349cbfccb48952499523d3de82ad5ced1f5ec664b67024e16f`) and the
  plugin-install evidence document under
  `var/distribution-install-readiness/s27-plugin/run-20260717T091437Z`.

## Notes

- Implementation was landed by earlier campaign commits; this record closes the
  row on verification evidence produced by the plan owner. The dedicated
  client-session half of the plugin smoke is credential-gated and tracked under
  the S38 CI row, not this bootstrap row.
