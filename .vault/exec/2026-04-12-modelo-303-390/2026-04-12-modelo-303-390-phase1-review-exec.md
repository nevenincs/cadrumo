---
name: modelo-303-390-phase1-review
description: Code review record for Modelo 303 + Modelo 390 builders (#62) per vaultspec-code-review skill
type: exec
tags:
  - "#exec"
  - "#modelo-303-390"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-modelo-303-390-phase1-task1-exec]]"
  - "[[2026-04-12-modelo-303-390-plan]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
---

# modelo-303-390 phase1 review

Issue: wgergely/aeat#62
Branch: `feature/62-modelo-303-390`
Review scope: every file changed in phase 1 task 1.

## Files reviewed

- `src/aeat/application/filing/__init__.py` — public API additions,
  `build_draft` threading of quarterly 303 drafts to the
  validator, `_extract_quarterly_303` helper.
- `src/aeat/application/filing/_builders/__init__.py` — registry growth.
- `src/aeat/application/filing/_builders/_modelo_303_schema.py` — static
  casilla collection for 303 v1 coverage.
- `src/aeat/application/filing/_builders/_modelo_390_schema.py` — static
  casilla collection for 390 v1 coverage.
- `src/aeat/application/filing/_builders/modelo_303.py` — `Modelo303Builder`.
- `src/aeat/application/filing/_builders/modelo_390.py` — `Modelo390Builder`.
- `src/aeat/application/filing/_validator.py` — `quarterly_303_drafts`
  kwarg, `_validate_quarterly_reconciliation` rule, supporting
  constants and helpers.
- `src/aeat/application/filing/testing.py` — `default_schema_provider`
  registers 130/303/390.
- `src/aeat/application/filing/test_modelo_303_390.py` — 21 unit tests.

## Review dimensions

### Casilla truth tables sourced from the Manual práctico IVA

✔ The 303 casilla table covers casillas 01-09, 28-45, 64-71
per the ADR. Every formula matches the Manual práctico IVA
2025 (AEAT), chapter "Modelo 303". The manifest is cited in
the ADR with sha256 `e4f80097…db18a3` and the BOE-published
Orden HAC/819/2024 modelo order is cross-referenced.

✔ The 390 casilla table covers the annual IVA devengado and
deducible totals plus the four annual-aggregate casillas
(84, 85, 86, 95), per the ADR. Formulas match the Manual
práctico IVA 2025 chapter "Modelo 390 declaración-resumen
anual" and BOE Orden HAC/1/2024.

✔ Non-goals (régimen simplificado, recargo de equivalencia,
REBU, intracomunitarias beyond deducible bases, importaciones
beyond deducible bases) are honoured — none of the excluded
casilla ranges appear in the schemas.

### Pydantic v2 strict mandate

✔ Every new boundary-crossing record re-uses the existing
`StaticCasillaSchema` / `StaticCasillaCollection` models, both
declared with
`ConfigDict(strict=True, frozen=True, extra="forbid")`.

✔ No dataclasses introduced. No bare `dict[str, Any]` on any
public signature — the `FilingInputs = Mapping[str, object]`
alias from the existing code is reused for builder inputs.

✔ Closed enumerations continue to use `StrEnum`
(`FilingValueKind`, `FilingDraftStatus`, `FilingFindingSeverity`).
No new enums were introduced — the existing set was sufficient.

### Cross-validation rigor (390 ↔ 303 × 4)

✔ `FilingValidator._validate_quarterly_reconciliation` runs
two independent checks:
1. Annual value vs Σ quarterly source with
   `Decimal("0.005")` tolerance — covered by
   `test_clean_reconciliation_has_no_mismatch_findings` and
   `test_mismatched_annual_value_emits_mismatch`.
2. 303 self-consistency on the three rate triples
   `(03, 01, 0.04)`, `(06, 04, 0.10)`, `(09, 07, 0.21)` —
   covered by
   `test_poisoned_303_internal_triggers_self_consistency_finding`.

✔ Both checks emit `FilingValidationFinding` records with
ERROR severity, stable machine codes, and complete trilingual
(`es` / `en` / `hu`) `Translatable` messages — covered by
`test_trilingual_message_keys_present`.

✔ The rule is gated on `draft.modelo == "390"` and a populated
`quarterly_303_drafts` tuple, so the 130/303 validation paths
are unchanged (confirmed by the unchanged
`test_filing.py` suite — 17 tests still green).

✔ Shape-validation of the four quarterly drafts at build time
is covered by `test_missing_quarterly_drafts_raises`,
`test_wrong_number_of_quarterly_drafts_raises`,
`test_quarterly_year_mismatch_raises`,
`test_ejercicio_required`.

### Typed signatures + Google-style docstrings

✔ Every public function, method, class, and module in the
new code carries a Google-style docstring with `Args`,
`Returns`, `Raises` sections where applicable. `ty` reports
no missing-docstring diagnostics.

✔ Every signature carries complete type hints. `ty` reports
no `invalid-return-type` or other diagnostics after the
`_extract_quarterly_drafts` narrowing fix.

### Error + logging discipline

✔ All domain errors inherit from `FilingComputationError`
which inherits from `FilingDraftError` → `AeatError`.

✔ No new exception classes were introduced — the existing
`FilingComputationError` covers every failure mode.

✔ Every new module uses `aeat.core.logging.get_logger(__name__)`.

### Public API discipline

✔ Callers reach the new builders via
`aeat.application.filing.build_draft(modelo="303"|"390", ...)`. The public
API adds three symbols to `__all__` — `Modelo303Builder`,
`Modelo390Builder`, `QUARTERLY_303_INPUT_KEY` — symmetric
with the existing `Modelo130Builder` export. No consumer
needs to reach into `aeat.application.filing._builders`.

### Testing discipline

✔ Every new test carries `@pytest.mark.unit`.
✔ Zero mocks, patches, fakes, stubs, or shadows — every
double is a frozen pydantic model conforming to the relevant
Protocol, or a real FilingDraft built by the real 303 builder.
✔ Tests are colocated in `src/aeat/application/filing/` per the Rust-style
convention.
✔ No live tests were added.

### Hygiene + gates

✔ `just lint` — clean.
✔ `just typecheck` — clean (ty).
✔ `just test` — 586 passed, 1 skipped (pre-existing),
  18 deselected. 21 new tests pass.
✔ `just hooks` — prek clean (ruff, ruff-format, ty, yaml,
  toml, large-files, merge-conflict, private-key,
  trailing-whitespace, end-of-files).

### In-flight sibling branch boundaries

✔ No changes under `src/aeat/domain/casillas/` (#23 territory).
✔ No changes to `pyproject.toml [tool.pytest]` or
  `conftest.py` (#15 territory).
✔ No changes to `src/aeat/core/i18n/` (#20 territory) — the
  `Translatable` type is consumed via `aeat.core.i18n.Translatable`
  as already imported by the filing schema.
✔ No new workflow files in `.github/workflows/` (GitHub
  Actions is permanently disabled on the repo per project
  rule).

## Outcome

**APPROVED.** All review dimensions pass. Proceeding to commit
and PR creation.
