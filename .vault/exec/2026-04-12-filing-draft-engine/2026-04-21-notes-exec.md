---
tags:
  - "#exec"
  - "#filing-draft-engine"
date: 2026-04-21
modified: '2026-04-21'
related: []
---
# Execution notes — Filing draft generation engine (#39)

Date: 2026-04-12
Branch: `feature/39-filing-draft-engine`

## What landed

- New subpackage `src/aeat/application/filing/` with the strict pydantic v2
  schema (`FilingDraftStatus`, `FilingValueKind`,
  `FilingFindingSeverity`, `FilingValue`,
  `FilingValidationFinding`, `FilingDraft`), the content-addressed
  `compute_draft_id` helper, the `FilingBuilder` ABC, the private
  `Modelo130Builder`, the `FilingValidator`, and the public
  `build_draft` / `validate_draft` / `iter_findings` entry points.
- Cross-module Protocols in `_protocols.py` cover modelo identity,
  casilla schema/collection/provider, deadline status/checker, and
  filing profile. All `@runtime_checkable`.
- Test-grade pydantic doubles in `aeat.application.filing.testing` (synthetic
  Modelo 130 schema, profile, deadline checker) — public so the
  CLI and downstream tests can consume them without reaching into
  private internals.
- New CLI sub-app `aeat filing` with `build`, `validate`, `show`,
  `list` wired into `aeat.entrypoints.cli.app`.
- Two new settings `AEAT_DRAFTS_DIR` and `AEAT_DRAFT_FAIL_ON_WARNING`,
  documented in `env/.env.example`. The alignment test in
  `tests/test_config.py` is green.
- 20 colocated unit tests covering the builder, validator, public
  API, JSON round-trip, stable hash, CLI smoke. No mocks/patches/
  fakes/stubs — Protocol-conforming pydantic doubles only.
- Vault research, ADR, and plan under `.vault/`.

## Code review

Reviewer: self (driver of this branch)

| Criterion | Outcome |
| --- | --- |
| Pydantic v2 strict for every Draft / Value / Finding / Validator output | ✅ Every boundary-crossing model uses `ConfigDict(strict=True, frozen=True, extra="forbid")`. |
| `draft_id` is deterministic and content-addressed | ✅ `compute_draft_id` hashes `(modelo, period, profile_tax_id, schema_version, sorted_values)` and excludes findings/status/timestamps. Tested by `test_stable_draft_id_for_same_inputs` and `test_compute_draft_id_excludes_findings_and_status`. |
| Every formula trace is structured, not free-form | ✅ `FilingValue.formula_trace` is `tuple[str, ...] | None` of casilla IDs. Builder populates it via `_computed_value`. Validator checks for divergence. |
| Typed signatures + Google-style docstrings | ✅ All public symbols. `ty` clean. |
| Errors inherit from `aeat.core.errors.AeatError` | ✅ `FilingDraftError`, `FilingBuilderError`, `FilingValidationError`, `FilingComputationError`. |
| Logging via `aeat.core.logging.get_logger(__name__)` | ✅ `_builders/modelo_130.py`, `_validator.py`, `__init__.py`, CLI. |
| Public API discipline — callers import from `aeat.application.filing` only | ✅ `_builders/`, `_builder.py`, `_validator.py`, `_schema.py`, `_protocols.py`, `_errors.py` are private. CLI imports the public surface only. |
| Lint / typecheck / tests / hooks all green | ✅ `ruff check .`, `ty check src tests`, full `pytest` (273 passed), `prek run --all-files`. |
| No bare `dict[str, Any]` in public signatures or persisted files | ✅ The CLI input parser does cast a JSON object into `dict[str, object]` internally for parameter coercion, but that boundary is the OS and not a persisted file. The public `FilingInputs` alias is `Mapping[str, object]`. |
| No mocks/patches/fakes/stubs in tests | ✅ Tests build real pydantic doubles via `aeat.application.filing.testing`. CLI tests use `monkeypatch.setenv` only to point at a temporary `AEAT_DRAFTS_DIR`. |
| Sibling-branch isolation (Protocol stubs for #6/#9/#23/#38) | ✅ No imports from `aeat.domain.modelos`, `aeat.domain.schema`, `aeat.domain.casillas`, `aeat.domain.deadlines`. Each is mediated by a Protocol. |

### Files changed

- `src/aeat/application/filing/__init__.py` (new)
- `src/aeat/application/filing/_schema.py` (new)
- `src/aeat/application/filing/_errors.py` (new)
- `src/aeat/application/filing/_protocols.py` (new)
- `src/aeat/application/filing/_builder.py` (new)
- `src/aeat/application/filing/_validator.py` (new)
- `src/aeat/application/filing/_builders/__init__.py` (new)
- `src/aeat/application/filing/_builders/_modelo_130_schema.py` (new)
- `src/aeat/application/filing/_builders/modelo_130.py` (new)
- `src/aeat/application/filing/testing.py` (new)
- `src/aeat/application/filing/test_filing.py` (new)
- `src/aeat/entrypoints/cli/filing/__init__.py` (new)
- `src/aeat/entrypoints/cli/filing/test_filing_cli.py` (new)
- `src/aeat/entrypoints/cli/__init__.py` (wire `filing` sub-app)
- `src/aeat/config.py` (`aeat_drafts_dir`, `aeat_draft_fail_on_warning`)
- `env/.env.example` (matching env vars)
- `.vault/research/2026-04-12-filing-draft-engine-research.md` (new)
- `.vault/adr/2026-04-12-filing-draft-engine-adr.md` (new)
- `.vault/plan/2026-04-12-filing-draft-engine-plan.md` (new)
- `.vault/exec/2026-04-12-filing-draft-engine/notes.md` (this file)

### Outcome

Approved. Ready to commit and open the PR.

## Follow-ups

- Replace `aeat.application.filing._protocols` with hard imports once the
  upstream subpackages (#6, #9, #23, #38) land on `main`. The
  rebase is bounded — search-replace on import lines plus a
  typing pass.
- Add per-modelo builders (303 IVA, 100 IRPF, ...) — one PR each.
- Wire `aeat.application.filing` into `aeat.adapters.persistence.storage` (#10) once the storage
  layer can persist arbitrary frozen pydantic models.
- Replace `aeat.application.filing.testing.default_schema_provider()` with the
  real `aeat.domain.casillas` provider once #23 is merged; the CLI
  defaults will need a follow-up to drop the synthetic helpers.
