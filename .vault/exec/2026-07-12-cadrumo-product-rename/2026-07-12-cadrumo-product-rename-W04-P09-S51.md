---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S51'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Validate the regenerated marketplace and plugin with the live strict Claude validator

## Scope

- `packaging/marketplace validation evidence`

## Description

- Run the repository plugin-validation smoke with the live Claude CLI.
- Validate the committed Cadrumo plugin subtree and marketplace root directly under strict mode.
- Assert the generated plugin name, source, distribution pin, MCP command, and environment interpolation.
- Reject former plugin, distribution, MCP, source-path, and product-copy residues in generated manifests.

## Outcome

Claude CLI 2.1.207 accepted all three strict validation surfaces. The repository
smoke returned `validated` after materialising 34 skills and 7 agents. Direct
strict validation passed for both `plugins/cadrumo` and the marketplace root.

Generated identity assertions confirmed plugin and MCP server `cadrumo`, source
`./plugins/cadrumo`, launcher `uvx`, pin `cadrumo[agent]==0.1.1`, executable
`cadrumo-mcp`, and the two `CADRUMO_MCP_*` user-config interpolations. The
focused former-product residue gate found no obsolete plugin, distribution,
MCP, source-path, or CLI branding in the three generated manifests.

## Notes

This evidence establishes strict manifest validation and generator identity
alignment only. It does not claim plugin installation, package publication,
network retrieval, MCP process startup, or end-to-end runtime behavior.

Formal review against the committed product-rename ADR and canonical
`PRODUCT_IDENTITY` found no unresolved finding. An unapproved executable
decision outside the committed governing chain was not used as acceptance
authority.

## Contextual-casing continuation

Claude Code 2.1.207 validated the checked marketplace and its ignored served
plugin directly under strict mode. Both commands returned exit code zero and
reported `Validation passed`. The standalone repository smoke materialised a
fresh plugin, reported `validated`, and strict-validated 34 skills and 7 agents
through the resolved Claude executable.

Three focused real-filesystem validation tests passed: fresh plugin strict
validation, checked marketplace scaffold parity with the live generator, and
fresh marketplace strict validation. The validated output carries `CADRUMO`
display and owner identities, `Cadrumo` sentence descriptions, lowercase
`cadrumo` plugin/source/server/distribution identities, `cadrumo-mcp`, and the
two `CADRUMO_MCP_*` environment interpolations.

This evidence proves current manifest schema acceptance, generator parity, and
generated-layout validity. It does not prove marketplace publication, network
retrieval, plugin installation, package availability, MCP process startup, or
an end-to-end operator session; those remain separate artifact and release
gates.
