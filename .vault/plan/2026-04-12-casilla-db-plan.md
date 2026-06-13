---
tags:
  - "#plan"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-research]]"
  - "[[2026-04-12-casilla-db-adr]]"
---

# Casilla DB implementation plan

This plan implements issue #23 on top of the current `main` branch state while respecting the explicit sibling-branch ownership rules supplied with the task.

## Proposed Changes

Introduce a new `aeat.domain.casillas` subpackage that owns the public casilla catalogue API, protocol stubs, JSON loader/saver/verification helpers, and Typer command group. Add the `AEAT_CASILLAS_ROOT` and `AEAT_CASILLAS_REVIEW_REQUIRED` settings, create canonical JSON catalogues for `MODELO_130`, `MODELO_303`, and `MODELO_390`, and add unit/live coverage plus a contributor reference doc for extending the corpus with a new modelo and period.

## Tasks

- Phase 1
  1. Scaffold `aeat.domain.casillas` package and protocol surfaces
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step1.md`
     - Executing agent: vaultspec-standard-executor
     - Details: Add `src/aeat/domain/casillas/` with public exports, strict pydantic models, Protocol stubs, errors, and package smoke tests.
  2. Implement loaders, verification, serialization, and config
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step2.md`
     - Executing agent: vaultspec-high-executor
     - Details: Add the JSON load/save/verify flow, wire settings/env alignment, and enforce duplicate/cross-reference/review checks.
  3. Wire CLI commands
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step3.md`
     - Executing agent: vaultspec-standard-executor
     - Details: Mount `aeat casillas` into the Typer root and implement `extract`, `translate`, `verify`, and `list`.
  4. Curate initial corpus files
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step4.md`
     - Executing agent: vaultspec-standard-executor
     - Details: Create canonical JSON files for `MODELO_130`, `MODELO_303`, and `MODELO_390` for 2025-complete periods with provenance and reviewer metadata.
  5. Add tests and documentation
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step5.md`
     - Executing agent: vaultspec-documentation
     - Details: Add colocated unit/live tests, CLI command-tree tests, config alignment checks, and a contributor-facing reference doc for adding a new modelo+period.
  6. Verify and review
     - Step summary: `.vault/exec/2026-04-12-casilla-db/2026-04-12-casilla-db-phase1-step6.md`
     - Executing agent: vaultspec-code-reviewer
     - Details: Run `just lint`, `just typecheck`, `just test`, and `just hooks`, then produce the mandatory code review audit covering every touched file and the issue-specific rules.

## Parallelization

Most of the coding work is sequential because the package API, config, CLI, and tests all depend on the same model surface. The documentation pass can begin once the CLI and verification workflow are stable.

## Verification

- `aeat.domain.casillas` public exports are complete and importable.
- `tests/test_config.py` remains aligned after adding the new env vars.
- Unit tests cover malformed records, dangling references, review-required enforcement, schema round-tripping, strict optional provenance typing, and trilingual Spanish-authoritative completeness.
- Live tests stay opt-in and avoid mocks.
- `just lint`
- `just typecheck`
- `just test`
- `just hooks`

## EXPLICIT PLAN REVIEW

- **Issue scope check**: The plan stays inside issue #23 by using a new `aeat.domain.casillas` package instead of touching `aeat.domain.schema`, by stubbing in-flight siblings behind Protocols, and by limiting the corpus to the three requested modelos.
- **Coordination check**: No work is planned inside `src/aeat/domain/modelos/`, `src/aeat/domain/schema/`, `src/aeat/adapters/outbound/llm/`, `src/aeat/domain/manuals/`, `src/aeat/domain/testing/`, or the sibling-owned corpus/manual areas.
- **Review outcome**: APPROVED for autonomous execution.
- **Approval note**: The repository’s normal human approval gate is satisfied here by the explicit user instruction to run the full vaultspec pipeline end-to-end with no human-in-the-loop pause.
