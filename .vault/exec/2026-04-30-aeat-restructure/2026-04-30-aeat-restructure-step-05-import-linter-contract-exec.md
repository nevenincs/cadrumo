---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-04-tier2-paths-guardrail-exec]]"
---

# 2026-04-30-aeat-restructure step-05 import-linter contract

## status

Step 5 PR 1 of N (Tooling prep). Lands the static import-boundary enforcement contract per ADR Implementation / Import-boundary enforcement section.

## scope

- Add `import-linter>=2.0` to `pyproject.toml` `dev` dependency group.
- Author `.importlinter` at repo root with three contracts:
  1. **Layered**: `aeat.entrypoints` ⊃ `aeat.application` ⊃ `aeat.adapters` ⊃ `aeat.domain` ⊃ `aeat.core`. Carve-out registry of 9 explicit `_repository.py` / `_service.py` files permitted to bypass `domain/` → `adapters/persistence/storage/`.
  2. **Independence**: `aeat.adapters.inbound`, `aeat.adapters.outbound`, `aeat.adapters.persistence` may not import each other.
  3. **Forbidden**: `aeat.core` is leaf (must not import from any other layer).

The contract activates fully when Step 7 keystone PR creates the layered destinations. Pre-Step-7 it parses cleanly and reports "no matches for ignored imports" warnings — expected, since the registered paths do not yet exist.

## verification

- `uv sync` resolves `import-linter==2.11` + `grimp==3.14`.
- `uv run lint-imports` parses the contract; pre-Step-7 reports missing-module warnings for the 9 carve-out entries (correct — they reference future paths). The contract structure itself is validated.

## next step

Step 5 PR 2 — shim-verification subroutine (`scripts/verify_shims.py` per ADR Shim-verification gate). Imports each declared shim path in a clean Python subprocess and asserts re-exported symbols are reachable. Used by Step 8 acceptance gate as the deterministic semver-rule precondition.

Subsequent Step 5 PRs:
- PR 3: rebase script (`scripts/rebase_imports.py`) + test fixture covering relative imports / TYPE_CHECKING / star imports / dynamic importlib / forward + reverse rewrite maps.
- PR 4: produce → verify → export end-to-end smoke test (CI-gating).
- PR 5: type-checker config (extend existing `[tool.ty]`) for new layered scope + zero-error baseline.
- PR 6: packaging verification CI job (`pip install -e .`, `pip install dist/*.whl`, post-install layer-import smoke).
