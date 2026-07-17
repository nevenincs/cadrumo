---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Re-run the installed tax and MCP oracles after D1 through D4 land and capture the corrected warm serving behavior as installed evidence and ## Scope

- `dev/packaging/installed_mcp_oracle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-run the installed tax and MCP oracles after D1 through D4 land and capture the corrected warm serving behavior as installed evidence

## Scope

- `dev/packaging/installed_mcp_oracle.py`

## Description

- Re-run the installed CLI tax oracle and the installed MCP oracle against the
  rebuilt release cohort after D1 through D4 landed.

## Outcome

- Installed CLI lane: the core packaging smoke passed end-to-end against the
  rebuilt cohort's root wheel (fresh venv install, digest-fragment-pinned,
  grounded Modelo 200 oracle `DP200014:00562 == 23000.00`); retained manifest
  under `var/packaging-smoke/core-20260717T150842Z`.
- Installed MCP lane: the MCPB client-install suite passed 4/4 against the
  rebuilt cohort through the real client runtime, including the self-healing
  bootstrap path, in 125 seconds — versus 428 seconds for the same suite
  before the campaign, the warm-serving and validation-skip work visible in
  the harness itself.

## Notes

- Executed by the plan owner directly. Both lanes consumed the S20 rebuilt
  cohort bytes without rebuilding.