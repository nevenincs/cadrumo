---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S57'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename packaging smoke labels, commands, and evidence artifacts

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Rename the packaging-smoke workflow, job, step labels, and uploaded evidence artifact to Cadrumo.
- Retain the host/core lane and explicitly execute the split-distribution and clean-Docker gates.
- Add a real-workflow structural test for canonical commands, evidence paths, and product identity.
- Reject the former executable and product spelling from the workflow surface.

## Outcome

The GitHub workflow now presents one Cadrumo packaging-smoke identity and runs
the canonical Linux/core, split-distribution, and Docker recipes. YAML parsing,
recipe dry-runs, Ruff, and six focused workflow/Docker structural tests pass.

## Notes

The focused real split-wheel installation test exceeds the bounded S57
structural-test window and was not needed to validate workflow wiring; its
canonical recipe is retained and resolves successfully through `just --dry-run`.
