---
tags:
  - "#plan"
  - "#filing-draft-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-filing-draft-engine-research]]"
---
# Plan — Filing draft generation engine (#39)

Date: 2026-04-12
Status: Approved (self-review, see Plan Review section below)
Branch: `feature/39-filing-draft-engine`

## Goal

Land the typed public API for `aeat.application.filing`, a `Modelo130Builder`
proof-of-concept, the cross-cutting validator, the `aeat filing`
CLI surface, and the colocated unit-test suite — all behind
Protocol stubs for in-flight sibling subpackages.

## Steps

1. **Schema layer** (`src/aeat/application/filing/_schema.py`)
   - Define `FilingDraftStatus`, `FilingValueKind`,
     `FilingFindingSeverity` as `enum.StrEnum`.
   - Define `FilingValue`, `FilingValidationFinding`, `FilingDraft`
     as strict pydantic v2 `BaseModel` with
     `ConfigDict(strict=True, frozen=True, extra="forbid")`.
   - Implement `compute_draft_id` as a pure function over the
     content tuple.

2. **Errors** (`src/aeat/application/filing/_errors.py`)
   - `FilingDraftError`, `FilingBuilderError`,
     `FilingValidationError`, `FilingComputationError` — all
     subclasses of `aeat.core.errors.AeatError`.

3. **Protocol stubs** (`src/aeat/application/filing/_protocols.py`)
   - `ModeloIdentity`, `CasillaSchema`, `CasillaCollection`,
     `CasillaSchemaProvider`, `DeadlineStatus`, `DeadlineChecker`,
     `FilingProfile`.
   - All `@runtime_checkable` so test doubles can satisfy them by
     duck-typing without inheritance.

4. **Builder ABC** (`src/aeat/application/filing/_builder.py`)
   - `FilingBuilder` ABC with `modelo_id` class attribute and
     `build(period, profile, inputs)` abstract method.

5. **Modelo 130 builder** (`src/aeat/application/filing/_builders/modelo_130.py`)
   - Concrete `Modelo130Builder` using a hand-curated casilla
     schema (`_modelo_130_schema.py`) that exercises every
     `FilingValueKind`.
   - Computes formula casillas in dependency order; populates
     `formula_trace` with the casilla IDs that fed the formula.
   - Raises `FilingComputationError` on dependency cycles or
     missing required inputs.

6. **Validator** (`src/aeat/application/filing/_validator.py`)
   - `FilingValidator` runs:
     - missing-required casilla → `casilla-required-missing`
     - out-of-range value → `casilla-out-of-range`
     - formula divergence → `formula-divergence`
     - deadline missed → `filing-deadline-missed`
     - schema-version mismatch → `filing-schema-version-mismatch`
   - Returns a tuple of `FilingValidationFinding`.

7. **Public API** (`src/aeat/application/filing/__init__.py`)
   - Re-export every public symbol.
   - `build_draft(modelo, period, profile, inputs, *, settings=None)`
   - `validate_draft(draft, *, settings=None)`
   - `iter_findings(draft, *, severity_at_least="WARNING")`
   - Module docstring with usage example.

8. **Settings + env** (`src/aeat/config.py`,
   `env/.env.example`)
   - Add `aeat_drafts_dir`, `aeat_draft_fail_on_warning`.
   - Mirror in `env/.env.example`.

9. **CLI** (`src/aeat/entrypoints/cli/filing/`)
   - Typer sub-app with `build`, `validate`, `show`, `list`
     commands.
   - Wired into `aeat.entrypoints.cli:app`.

10. **Tests** (`src/aeat/application/filing/test_filing.py`,
    `src/aeat/entrypoints/cli/filing/test_filing_cli.py`)
    - Builder against synthetic schemas + hand-curated inputs.
    - Validator against synthetic drafts.
    - End-to-end smoke for Modelo 130.
    - JSON round-trip for `FilingDraft`.
    - Stable `draft_id` hash test.
    - CLI smoke via Typer's `CliRunner`.
    - Real Protocol-conforming concrete test doubles, no mocks.

11. **Vault exec record** at
    `.vault/exec/2026-04-12-filing-draft-engine/notes.md`.

12. **Lint / typecheck / test / hooks** all green via `just`.

13. **Self code review** against the criteria in the issue
    bootstrap.

14. **Commit + push + PR**.

## Plan Review

Reviewer: Claude (driver of this branch)
Date: 2026-04-12

### Findings

- Schema shape matches issue spec exactly. The decision to keep
  `FilingDraftStatus` as the full lifecycle enum (not just the
  PoC subset) was confirmed in the ADR; downstream consumers can
  pin imports now.
- `compute_draft_id` deliberately excludes `created_at`,
  `updated_at`, `findings`, `status`, and `notes`. This means
  re-validating a draft (which only updates findings/status/
  `updated_at`) preserves identity — required for idempotent
  submission retries downstream.
- Protocol stubs are `@runtime_checkable` so the test doubles
  can satisfy them by structural typing. This is the only sane
  way to honour the "no mocks/patches/fakes/stubs in tests"
  rule while still keeping cross-module isolation.
- The `_builders/` private package is the right boundary —
  callers from outside `aeat.application.filing` cannot reach the concrete
  Modelo 130 implementation. The public registry hides the
  selection logic.
- Tests are colocated under `src/aeat/application/filing/` per the
  Rust-style convention enforced by CLAUDE.md.
- All settings additions are documented in `.env.example` and
  the alignment test will catch drift.

### Outcome

Approved. Proceed to execution.

## Risks

- The Protocol stubs for `aeat.domain.casillas` / `aeat.domain.schema` /
  `aeat.domain.deadlines` will need a small rebase once those
  subpackages land. The cost is bounded — it is a search-replace
  on the import lines plus a typing pass.
- Windows-only `just` execution: `prek run --all-files` is the
  most likely point of friction; if it surfaces line-ending or
  EOL hooks the fix is to normalise files in the worktree, not
  to skip the hook.
