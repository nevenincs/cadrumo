---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0553c5540697c98b20ad0924469cfe380c95e6067cc942e9feb7e4a048f3f73e'
step_id: 'S36'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Test sealed release artifacts across supported stable runtimes

## Scope

- `.github/workflows/publish.yml`

## Changes

- `M` `.github/workflows/publish.yml`
- `verify:` `actionlint .github/workflows/publish.yml; uv run --no-sync pytest -q dev/ci/tests/test_workflow_tool_invocation.py -o addopts='' -n 0` -> `pass`
- `verify:` `uv run --no-sync python -c "from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); assert [row.minor for row in inventory.stable] == ['3.13', '3.14']; assert inventory.next.phase.value == 'prerelease'; assert not inventory.next.classifier_eligible"` -> `pass`
