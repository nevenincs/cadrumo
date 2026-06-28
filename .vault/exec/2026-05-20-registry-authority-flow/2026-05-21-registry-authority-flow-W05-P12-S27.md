---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S27'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P12.S27`

Profiled registry test collection and load hot paths.

- Modified: this execution record

## Description

Measured collection, recursive registry fingerprinting, full registry loading,
and snapshot construction to separate real calculation cost from avoidable
test orchestration cost.

Collection is not the bottleneck: `uv run pytest
src/aeat/domain/calculations/registry --collect-only -q` collected 1,801 tests
in 1.16s.

The suspicious cost is repeated committed-registry loading. Direct timing showed
`_collect_registry_tree_fingerprints(root)` averaging about 3.52s across 10
runs, `load_registry_tree(root)` averaging about 4.63s with an 18.26s max, and
Modelo 303 snapshot construction averaging about 0.081s. The calculation and
snapshot layer is not computationally exceptional; repeated tree walks are the
hot path.

## Tests

`uv run pytest src/aeat/domain/calculations/registry --collect-only -q` passed
with 1,801 collected tests in 1.16s.
