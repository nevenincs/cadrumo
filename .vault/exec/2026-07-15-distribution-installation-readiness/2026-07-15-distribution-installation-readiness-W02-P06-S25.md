---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:acb8cb01ed54cc6255361374629981e3e2b5268ae95f8ad3a53ec1219d871865'
step_id: 'S25'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

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
