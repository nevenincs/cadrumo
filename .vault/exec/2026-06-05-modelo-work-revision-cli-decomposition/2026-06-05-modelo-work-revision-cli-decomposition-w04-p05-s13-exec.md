---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S13'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P05.S13 Execution

Inventoried the residual `_app_live.py` monolith guard offender.

Findings:
- `_app_live.py` was 2262 lines against a 2117-line frozen budget.
- The smallest coherent extraction that clears the budget is the read-only `borrador 100` subgroup.
- The subgroup already delegates snapshot policy and persistence to `Borrador100SnapshotService`; extracting it does not move live policy into CLI.

Discovery:
- Exact `rg` over `_app_live.py` found `borrador_100_app`, `borrador_100_list`, `borrador_100_show`, and `borrador_100_latest`.
- `vaultspec-rag` semantic search for live borrador commands identified the same command group.
