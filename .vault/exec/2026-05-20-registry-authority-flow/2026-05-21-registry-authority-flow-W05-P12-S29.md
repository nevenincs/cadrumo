---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S29'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P12.S29`

Established the suspicious-performance gate budget.

- Modified: `.vault/plan/2026-05-20-registry-authority-flow-plan.md`
- Modified: this execution record

## Description

Set the registry performance posture for this rollout:

- Collection budget: registry package collection should stay under 5s on the
  local Windows `uv` workflow. Current evidence is 1,801 tests collected in
  1.16s.
- Focused M200 hardening gate budget: the reviewability gate plus
  `test_modelo_200_registry.py` should stay under 60s. Current evidence is 8
  tests in 22.57s.
- Chunk budget: no ordinary sorted registry chunk should take multiple minutes
  without an explicit owning step. Current evidence still breaches this budget:
  files 85..89 took 362.83s for 168 tests.

Added `W05.P12.S30` to track reducing the remaining slow registry chunk rather
than hiding the breach behind a completed rollout.

## Tests

`uv run pytest src/aeat/domain/calculations/registry --collect-only -q` passed
with 1,801 collected tests in 1.16s.

`uv run pytest
src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable
src/aeat/domain/calculations/registry/test_modelo_200_registry.py -q
--tb=short` passed with 8 tests in 22.57s.
