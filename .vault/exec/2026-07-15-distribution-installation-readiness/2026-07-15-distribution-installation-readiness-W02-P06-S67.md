---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S67'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Inventory generated harness identifiers and compare `cadrumo-` names plus MCP product identities with the accepted tuple

## Scope

- `dev/packaging/verify_distribution_identity.py`
- `src/cadrumo/_data/agent`
- `src/cadrumo/agent`
- `src/cadrumo/entrypoints/mcp`

## Description

- Inventory the real authored personas, skills, and rules from the shipped harness accessors.
- Materialise and inspect the production Claude workspace, plugin, and marketplace generators in temporary directories.
- Run the production MCP server, prompt, and resource projections in an isolated Cadrumo storage root.
- Compare every emitted identifier with the literal `cadrumo-` requirement and every MCP product surface with the accepted tuple.
- Add real-behaviour tests that import the verifier and invoke its command-line entry point without substitutes or code mutation.

## Outcome

The verifier completed and returned exit status `1`, correctly refusing the current
namespace. The authored authority contains seven personas, 34 skills, and seven rules;
none carries the required `cadrumo-` prefix. The generated workspace, plugin, and
marketplace preserve those generic identifiers. The MCP surface exposes 35 prompt names,
48 concrete harness-resource leaves, and 35 prompt-embedded harness-resource leaves; the
34 skill prompts and every harness-resource leaf remain unprefixed. Six MCP resource
templates already carry the product prefix. Exact-set parity between every authored
inventory and its workspace, plugin, marketplace, prompt, and resource projection passed.
The 18 parity checks include generated agent and skill metadata plus each skill prompt's
embedded-resource association, rather than filenames and aggregate counts alone.

The independent MCP product identity comparison passed. The human executable is `aeat`,
the server and plugin identifier are `cadrumo`, the MCP executable is `cadrumo-mcp`, the
tool prefix is `cadrumo_`, and the resource scheme is `cadrumo://` across canonical,
project-script, runtime-server, generated plugin, generated marketplace, MCPB, tool, and
resource projections.
The MCP tool comparison inventories all runtime command and meta-SDK tools plus the MCPB
tool declarations. It accepts only `cadrumo_` or the closed generic progressive-discovery
set `describe`, `execute`, `search`, and `toolsets`; all 304 observed projections passed.

Focused Ruff formatting and lint checks passed. All four focused real-behaviour tests
passed, including the actual command-line process returning nonzero with the JSON failure
report and rejection of a mixed-revision repository root. The retained verifier report
contains 302 namespace observations at
`var/distribution-install-readiness/s67-identity/distribution-identity.json` with SHA-256
`35c3f71dec46dd31c3def356f6e2d23ad2edfeae198cade941ef3296d5f8183f`.

## Notes

This verification step made no harness rename, translation, alias, or generated-artifact
mutation. MCP imports initially encountered the operator workstation's incompatible
retired local database; the verifier now executes the real MCP projection in a child
process with a fresh temporary Cadrumo storage root and a repository-owned import path,
so repository identity verification does not depend on ambient taxpayer state or combine
two source revisions.

Formal code review initially found three completeness gaps in projection parity, MCP
surface coverage, and revision isolation. All three were remediated and the final
read-only re-review passed with no remaining S67 finding. The rolling audit preserves
both the findings and their final dispositions.

The observed prefix failure is the intended honest result. Step S67 remains unchecked,
and the affected Claude artifacts and downstream release claims remain blocked pending a
separately authorised namespace migration. Bilingual product-description verification is
owned by Step S68 and was not treated as satisfied here.

- CLOSED (2026-07-18): the operator-approved `distribution-harness-identity`
  migration (plan 2026-07-18, 12/12 closed) brought every harness identifier
  under the `cadrumo-` prefix and every client-display description to
  six-claim English/Spanish parity; `verify_distribution_identity` now exits 0
  across all surfaces (retained evidence
  `var/distribution-install-readiness/s11-migration-identity-bilingual/`,
  model-facing digest `a025188a4d…`). The verification this step implemented
  passes for real, so the row closes on that green verdict.

