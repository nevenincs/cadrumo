---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-04-tier2-paths-guardrail-exec]]"
---

# 2026-04-30-aeat-restructure step-05 import-boundary contract

## status

Step 5 PR 1 of N (Tooling prep). Originally landed an external `import-linter` contract. Superseded by the delivered hard-cutover, which uses pytest import-contract tests plus `ty` static resolution instead of retaining `.importlinter`.

## scope

- Historical scope before supersession:
  - Add `import-linter>=2.0` to `pyproject.toml` `dev` dependency group.
  - Author `.importlinter` at repo root with three contracts:
  1. **Layered**: `aeat.entrypoints` ⊃ `aeat.application` ⊃ `aeat.adapters` ⊃ `aeat.domain` ⊃ `aeat.core`. Carve-out registry of 9 explicit `_repository.py` / `_service.py` files permitted to bypass `domain/` → `adapters/persistence/storage/`.
  2. **Independence**: `aeat.adapters.inbound`, `aeat.adapters.outbound`, `aeat.adapters.persistence` may not import each other.
  3. **Forbidden**: `aeat.core` is leaf (must not import from any other layer).

Delivered scope after hard-cutover:
- `.importlinter` and the external dependency are not present in the accepted tree.
- `tests/import_contract/test_adr_layout_import_smoke.py` asserts canonical packages import, deleted root modules remain absent, representative public symbols live at canonical paths, and old locations do not reappear.
- The named carve-out registry remains explicit in ADR text and import-contract tests rather than an `ignore_imports` plugin registry.

## verification

- Historical verification: `uv sync` resolved `import-linter==2.11` + `grimp==3.14`, and `uv run lint-imports` parsed the contract before supersession.
- Delivered verification: the hard-cutover import-contract tests replaced this gate.

## next step

Step 5 PR 2 was the historical shim-verification subroutine. It was later superseded by the hard-cutover import-contract model: canonical imports are verified directly and deleted root modules must remain absent.

Subsequent Step 5 PRs:
- PR 3: rebase script (`scripts/rebase_imports.py`) + test fixture covering relative imports / TYPE_CHECKING / star imports / dynamic importlib / forward + reverse rewrite maps.
- PR 4: produce → verify → export end-to-end smoke test (CI-gating).
- PR 5: type-checker config (extend existing `[tool.ty]`) for new layered scope + zero-error baseline.
- PR 6: packaging verification CI job (`pip install -e .`, `pip install dist/*.whl`, post-install layer-import smoke).
