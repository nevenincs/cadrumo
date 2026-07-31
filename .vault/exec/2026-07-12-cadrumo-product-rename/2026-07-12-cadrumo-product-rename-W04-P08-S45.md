---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:ce5bf625b84dbe079ae521997499a8b778c40afee6f5f4b707d990c2d4ee8049'
step_id: 'S45'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename MCP prompts and product-facing tool copy

## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py`

## Description

- Rename the orientation prompt's machine identity to `cadrumo-empezar` and its
  user-facing title and operating brief to sentence-prose Cadrumo.
- Delegate embedded prompt URI construction to the canonical MCP resource helper.
- Preserve AEAT wording only where it denotes the Spanish tax authority, its
  period codes, or the filing counterparty; use `aeat` only for a human CLI
  invocation if prompt copy ever cites one.
- Prove Cadrumo prompt names, copy, and embedded resource URIs through the real prompt and server surfaces.

## Outcome

MCP guided prompts expose machine prompt name `cadrumo-empezar`, user-facing
`Cadrumo` prose, and the canonical `cadrumo://skill/...` and
`cadrumo://rule/...` resource contracts without a duplicate URI-scheme
authority. Workflow arguments describe the AEAT period code, and workflow
briefs state that the taxpayer files with AEAT themselves; those are external
authority references, not product aliases.

The real MCP SDK prompt list/get/completion handlers and the SDK-independent
catalogue/document surface pass together. Existing assertions now pin the AEAT
period and filing-counterparty meanings as well as the product and URI tuple.

## Notes

The two prompt-test URI expectations originated with the concurrent S44
resource-scheme change. The S44 owner confirmed `resource_uri` as the final
constructor and explicitly transferred those cohesive assertions to S45; no
changes were made to `_resources.py` in this step.

No prompt currently cites a human CLI command. If one does, the binding ADR
requires `aeat`; lowercase `cadrumo` remains reserved here for prompt and URI
machine identities.

Thirty-four focused prompt, resource, harness-delivery, and real-client MCP
tests pass. Ruff, formatting, and Ty pass on the prompt source and direct test
surface.
