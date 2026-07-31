---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:ea86e1a2cdb558810f75eead12a4016444a569ce446504d29332e65d5157722d'
step_id: 'S14'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget error-registration module paths and structural assertions

## Scope

- `src/cadrumo/core/errors registries`

## Description

- Ground the class-key registry and its enforcement walkers through semantic discovery and whole-file reads.
- Retarget product-qualified registry keys and structural links to `cadrumo` without changing error codes or locale keys.
- Preserve the nested `adapters.outbound.aeat` authority segment in every external-authority exception key.
- Retarget package walkers and assertions so enforcement traverses the relocated Cadrumo tree without an alias.

## Outcome

Retargeted all 566 declared exception-class keys to the Cadrumo package root.
The registry now has 566 unique declared rows and 566 error-code rows, with zero
class keys beginning `aeat.`. Twenty-seven AEAT adapter keys correctly retain
their authority segment as `cadrumo.adapters.outbound.aeat.*`; no key contains
the invalid product-like `cadrumo.adapters.outbound.cadrumo` shape.

Registry shard docstring links, the circular-import explanation, the exception
base-hygiene walker, and the full registry-enforcement walker now name and walk
`cadrumo`. No old registry row, alias row, dual package traversal, or fallback
was added. Error codes and message keys containing `AEAT` remain unchanged
because they are stable error taxonomy or authority-facing locale semantics,
not import targets.

## Notes

- Direct import smoke passed and resolved `cadrumo.core.errors.CoreError` to `ERROR_AEAT_CORE`. Five focused registry primitive tests passed; focused Ruff E/F checks, formatting, and residue checks passed.
- The relocated import-all enforcement tests now traverse `cadrumo`, but execution reaches a separate open rename residue in `core.i18n._render`, which still requests package resources from `aeat`. The repository-root pytest hook has the same former-package dependency. Those files are outside the error-registry area and were not changed; the failure is recorded rather than bypassed with a shim or test shortcut.
