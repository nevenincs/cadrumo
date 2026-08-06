---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:0beadd3cde2269553860ec8057cfe33630040dd3be9e7b70d6d74f755b13ce7d'
step_id: 'S10'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Move package-local tests and direct imports without shadow modules

## Scope

- `src/aeat tests to src/cadrumo tests`

## Description

- Confirm the S09 move already relocated the complete package-local test tree.
- Retarget static imports, dynamic module strings, source-root paths, and import-contract scanners from `aeat` to `cadrumo`.
- Preserve the nested AEAT authority adapter, registry taxonomy, official URLs, and authority terminology.
- Compile the relocated tree and run scoped syntax-grade Ruff, format, and direct-import residue checks.

## Outcome

Reconciled 2,005 former product-root occurrences across 478 test, conftest,
fixture-support, and agent-eval-test Python files. No second filesystem move was
needed because S09 had already relocated these files under `src/cadrumo`.

The resulting test surface has zero static `from aeat` or `import aeat`
statements, zero old-root `__import__` or `import_module` targets, zero
`src/aeat` or `SRC_AEAT` package-root references, and zero structural
`("src", "aeat", ...)` path assertions. Import inventory helpers and their
ratchet baselines now scan and report the Cadrumo namespace.

The remaining 2,869 test lines containing lowercase `aeat` are classified as:

- authority-owned adapter paths, registry taxonomy, official URLs, credentials,
  legal provenance, and AEAT-facing terminology that must remain;
- CLI executable/help identity deferred to S25;
- distribution, wheel, resource, and release metadata deferred to S11 and S24;
- persistence identity deferred to S18 through S22;
- MCP, plugin, and marketplace identity deferred to S43 through S54.

Verification passed for full-tree AST compilation, Ruff syntax/undefined-name
rules (`E9`, `F63`, `F7`, `F82`) over every changed file, Ruff format checks,
the zero direct-import residue search, and whitespace validation. The first
mechanical pass briefly interpreted 22 local `aeat.domains` authority-variable
accesses as package imports; the scoped Ruff check exposed two executable
instances and the residue audit found the whole class. All 22 were restored to
the authority variable before completion.

## Notes

Broad pytest was intentionally not run before S13 because production dynamic
imports and other executable package-root strings remain assigned to that Step.
Full default Ruff also reports pre-existing documentation-rule debt throughout
the large test corpus; the syntax-grade rules and format checks relevant to this
mechanical rename are green. No production Python outside test/eval-test paths
was modified.
