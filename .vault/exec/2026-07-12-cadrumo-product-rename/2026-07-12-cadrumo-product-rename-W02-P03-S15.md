---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Preserve the external authority adapter name under the new product root

## Scope

- `src/cadrumo/adapters/outbound/aeat`

## Description

- Preserve `cadrumo.adapters.outbound.aeat` as the external authority boundary under the Cadrumo product root.
- Correct the Sede public API example so it references the preserved authority package.
- Verify representative authority packages and the registry-facing declaration observation target import directly.
- Confirm the removed top-level `aeat` package and a product-named outbound authority package do not resolve.
- Scan adapter and registry surfaces for product-named outbound paths and old top-level imports.

## Outcome

The external authority adapter remains at `src/cadrumo/adapters/outbound/aeat`; 141 Python files are present beneath that boundary and no `outbound/cadrumo` directory exists. Direct imports succeeded for the authority root plus its `auth`, `browser`, `sede`, `verify`, and `export` packages. The registry-facing `capture_filed_declaration_observation` export resolved to its concrete Sede implementation. Exact residue checks returned zero forbidden paths or imports. Ruff check, Ruff format check, and bytecode compilation passed for the corrected adapter file.

## Notes

The adapter layout was already structurally correct from the earlier package move. This step changed only a stale public API example that named the nonexistent `cadrumo.adapters.outbound.cadrumo` package. Official AEAT authority names, classes, prose, and URLs were intentionally retained.
