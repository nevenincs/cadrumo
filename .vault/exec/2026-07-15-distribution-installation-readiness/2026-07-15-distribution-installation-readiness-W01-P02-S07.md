---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:74c3124620e089a14f579ba66beab2a894606d61540f1ed6ab1dd04386a92eeb'
step_id: 'S07'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Execute the public MCP protocol itinerary and assert the same grounded Modelo 200 result

## Scope

- `dev/packaging/installed_mcp_oracle.py`

## Description

- Launch the absolute installed `cadrumo-mcp` executable with product scripts absent from `PATH`.
- Drive initialize, tool discovery, profile creation, identity confirmation, work creation,
  calculation, persisted-observation lookup, and resource reading through the public MCP SDK.
- Reuse the CLI oracle's exact tax-value, formula, legal-reference, source-reference, notice, and persistence assertions.
- Consume the cold-session identity behavior delivered separately by `W01.P02.S61`.

## Outcome

- A freshly built wheel and both exact companion wheels installed into a new Python 3.13 environment with the agent extra.
- The installed MCP server advertised the required tools and executed the complete Modelo 200 itinerary without checkout imports or executable lookup.
- Five real MCP calls proved profile creation, cold-session identity, work creation,
  calculation, and persisted-observation retrieval before following the returned resource.
- The resource-linked persisted observation proved `DP200014:00562=23000.00`, formula
  `modelo-200-cuota-integra`, the sole expected warning, and authoritative legal and source
  references.
- Ruff, ty, Python compilation, the focused workflow/MCP regression suite, and the real
  installed-artifact oracle passed.

## Notes

- The first artifact run exposed that long-running MCP identity reads lacked an active bucket
  session after profile creation. That defect and its real custody regression were isolated and
  committed as `W01.P02.S61` before this step was re-executed.
- Review findings were resolved by rejecting warning notices outside calculation and by obtaining
  persisted revision, work-unit, count, and resource identities from the public
  `modelo.work.observations` command instead of reconstructing them in the oracle.
- Final retained evidence was generated from a committed archive snapshot under
  `var/distribution-install-readiness/s07-final-4`.
