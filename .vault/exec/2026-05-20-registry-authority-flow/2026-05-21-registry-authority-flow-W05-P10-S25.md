---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S25'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P10.S25`

Verified M200 registry and fragment-size gates.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness-manifest.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml`
- Modified: this execution record

## Description

Ran the global registry TOML reviewability gate and Modelo 200 registry tests.
The gate now runs with `_MAX_TOML_FRAGMENT_LINES = 1_750`. It passed against
the split Modelo 200 registry fragments and the compacted Modelo 100 manifest
state, confirming the stricter committed reviewability threshold is satisfied.

## Tests

`uv run pytest -q
src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable
src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned
src/aeat/domain/calculations/registry/test_modelo_200_registry.py
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py` passed
with 10 tests in 28.58s.

The committed registry line-count sweep found no TOML fragments over 1,750
lines.
