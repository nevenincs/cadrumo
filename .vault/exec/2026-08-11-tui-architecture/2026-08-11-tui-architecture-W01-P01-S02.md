---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:038d384e40e6d78bbeac2e864ce4820168937fdf07fb340946e3b1698cf7bb5b'
step_id: 'S02'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enforce the hexagonal TUI boundary, launcher-only adapter wiring, and backend prohibition contracts

## Scope

- `.importlinter`

## Description

- Ground the boundary in D11, the canonical layered contract, and semantic RAG discovery before changing configuration.
- Add one backend-to-TUI prohibition without redeclaring the existing lower-layer and adapter direction contract.
- Add the launcher-only direct adapter-wiring exception, component implementation independence, and feature implementation independence.
- Prove the contracts against real temporary Python package graphs, including one accepted topology and one rejected edge per contract.

## Outcome

The canonical Import Linter configuration now declares four TUI-specific contracts. The existing `layered` contract remains the sole general hexagonal direction authority; the new contracts narrow only the facts it could not express: no backend or sibling entrypoint may depend on the dedicated TUI, only `launcher` and its descendants may directly wire adapters, component implementations cannot reach features or backend layers, and operation/profile/secret/flow implementations remain mutually independent.

Wildcard source expressions intentionally keep the gate runnable before `cadrumo.entrypoints.tui` is created. The launcher exception names both the adapter package and descendants because Import Linter distinguishes a bare package import from `package.**`. Dynamic imports, type-only reaches, facade/re-export rules, Textual location, and non-Python discovery remain exclusively assigned to W01.P01.S03 rather than duplicated here.

Focused verification:

    uv run --no-sync lint-imports --contract tui-backend-prohibition --contract tui-launcher-only-adapter-wiring --contract tui-components-independent --contract tui-feature-independence --no-cache
    Contracts: 4 kept, 0 broken.
    Analyzed 4786 files, 23966 dependencies.

    uv run --no-sync pytest -q -n 0 -m integration dev/tests/test_importlinter_tui_boundaries.py
    8 passed in 0.73s

    uv run --no-sync ruff check dev/tests/test_importlinter_tui_boundaries.py
    All checks passed!

    uvx vaultspec-core vault check all
    Exit code: 0 in 31.3s
    Vault Check - All: structure, frontmatter, markdown, links, dangling, body-links, placeholders, orphans, feature-rename-integrity, references, adr-status, modified-stamp, rename-integrity, and encoding clean; 1303 shared warnings (1 annotations, 7 features, 53 exec-mapping, 1213 body-sections, 29 schema).

## Notes

S02 remains open and uncommitted pending independent review. No broad gate was run at this stage. The mutation-sensitive suite independently proves that a non-entrypoint application backend and MCP reject direct TUI imports, that a launcher descendant accepts an adapter-descendant import, and that a non-launcher TUI module rejects the same adapter-descendant shape. The first default pytest invocation used the repository's unit-only marker selection and therefore did not execute these integration tests; the recorded command is the explicit successful integration route. An intermediate in-process fixture run resolved the installed editable `cadrumo` package instead of its temporary graph; the final test uses a dedicated package root while preserving the live contract definitions, preventing that namespace collision without mocks or patches.
