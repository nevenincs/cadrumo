---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S02'
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
---

# `schema-hardening-m131-fragmentation` `P01.S02`

Mechanically split Modelo 131 revision files into generic revision-fragment
directories without changing loader code or registry schema semantics.

- Modified: `src/aeat/_data/registry/aeat/modelos/131/revisions`

## Description

The four source revision files were replaced by four fragment directories:
`2019-2023`, `2024`, `2025`, and `2026`. Each directory now contains
`revision.toml` plus section fragments for parameters, casillas, bindings,
formulas, export layouts, extraction profiles, live references, verification
expectations, constructs, application links, completeness manifests, and the
2026 deadline windows.

The split preserved the current shared-worktree registry content. That content
already included selector bound edits on the M131 previous-filing bindings, but
`42e9cd4dc` is the first Git commit that contains those fields. No per-modelo
loader rule was added.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_131_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
