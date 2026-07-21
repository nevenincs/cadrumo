---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S57'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename packaging smoke labels, commands, and evidence artifacts

## Scope

- `.github/workflows/packaging-smoke.yml`
- `dev/packaging/tests/test_packaging_smoke_workflow.py`

## Description

- Rename the packaging-smoke workflow, job, and step labels to sentence-prose
  Cadrumo, and uploaded evidence artifacts to lowercase machine `cadrumo`.
- Retain the host/core lane and explicitly execute the split-distribution and clean-Docker gates.
- Add a real-workflow structural test for canonical recipes, evidence paths,
  product identity, and the binding human-executable boundary.
- Reject former package/import identity and `cadrumo` as a human command without
  banning the valid `aeat` executable from command contexts.

## Outcome

The GitHub workflow presents sentence-prose `Cadrumo Packaging Smoke` labels,
uses machine job and evidence names `cadrumo-packaging-smoke` and
`cadrumo-packaging-smoke-evidence`, and runs the canonical Linux/core,
split-distribution, and Docker recipes. Those recipes own the installed-product
probes and invoke the sole human CLI as `aeat`; the workflow does not introduce
a direct `cadrumo` human command.

The structural contract separates labels from commands: `aeat` remains invalid
as product branding or a former package/import root, but remains valid as the
binding executable in a command context. The guard inspects every shell line
and command segment, including environment- and `uv run` option-prefixed
executables. Former imports including comma-separated imports, `python -m`
modules, install targets, `aeat-data` distribution families, source roots, and
packaging paths are rejected contextually.

## Notes

The focused real split-wheel installation test exceeds the bounded S57
structural-test window and was not needed to validate workflow wiring; its
canonical recipe is retained and resolves successfully through `just --dry-run`.

YAML parsing and 19 S57 workflow guard cases pass. The combined S57/S58
workflow identity surface passes 44 cases. The Linux/core, split-distribution,
and Docker recipe dry-runs, Ruff, formatting, and Ty also pass.
