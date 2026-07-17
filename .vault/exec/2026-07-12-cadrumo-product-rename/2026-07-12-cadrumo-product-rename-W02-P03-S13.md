---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget dynamic imports to public Cadrumo facades

## Scope

- `src/cadrumo dynamic import sites`

## Description

- Ground dynamic import and public facade rules against representative production epicenters.
- Retarget qualified product module references and importlib targets without changing authority identifiers.
- Exclude tests, eval tests, persistence namespaces, cryptographic contexts, settings, and S14 error registries.
- Verify syntax, focused lint, formatting, residue, plan state, and import smoke.

## Outcome

Retargeted 86 product-qualified module references across 16 production Python files. The changed set covers three literal `importlib` targets, payload package discovery, registry cross-domain checks, public-facade examples, service-owner metadata, logger/module identifiers, and qualified annotations. `adapters.outbound.aeat`, `registry/aeat`, AEAT URLs/prose, persisted namespaces, retained settings, and error registry declarations remain unchanged.

## Notes

- A first candidate rewrite was deliberately rolled back from non-module strings after review; the final diff contains only the 16 classified module-reference files.
- All 16 files passed compileall, Ruff `E9/F63/F7/F82`, and format checks. The uv-environment import smoke reaches `cadrumo.core` and then stops at the expected S14 error-registry mismatch for `cadrumo.core.errors.CoreError`; error registry reconciliation was not pulled forward.
