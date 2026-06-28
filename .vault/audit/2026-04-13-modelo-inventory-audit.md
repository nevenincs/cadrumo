---
name: 2026-04-13-modelo-inventory-audit
description: Mandatory code review for the modelo inventory + pydantic registry under aeat.domain.modelos (#108)
type: audit
tags:
  - "#audit"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
  - "[[2026-04-13-modelo-inventory-research]]"
---

# modelo-inventory audit (#108)

- Date: 2026-04-13
- Branch: feature/108-modelo-inventory-catalogue
- Commit range: main..HEAD (9 commits)

## Scope

All 41 files / +2769 lines touched by the 9 exec commits. Key files:
- src/aeat/domain/modelos/__init__.py, _codes.py, _categories.py, _citations.py,
  _applicability.py, _metadata.py, _errors.py, _registry.py, _cli.py
- src/aeat/domain/modelos/_entries/_common.py + 20 per-modelo entries
- src/aeat/domain/modelos/test_{codes,registry,applicability,citations,metadata,cli,casilla_cross_reference}.py
- src/aeat/entrypoints/cli/modelos/__init__.py, src/aeat/entrypoints/cli/__init__.py (2-line wire-up),
  pyproject.toml (1-line B008 per-file ignore for _cli.py)

## Gate outcomes

just lint       -> All checks passed!
just typecheck  -> All checks passed!
just test       -> 756 passed, 1 skipped, 23 deselected in 29.95s
just hooks      -> all prek checks Passed (trailing ws, end-of-files, yaml, toml, ruff, ruff format, ty type check)

All four gates green on Windows.

## Findings

### 1. Registry-completeness invariant - OK
_finalise_registry checks missing=set(ModeloCode)-materialised,
extra=materialised-set(ModeloCode), per-entry code is key, and duplicate
entry, each raising RegistryIntegrityError. test_registry_completeness
asserts set equality both directions; sensitive.

### 2. Caps-into integrity - OK
_check_caps_into iterates all entries at import and raises on unresolved
target. Live-sweep test plus synthetic dangling test (one-entry dict with
caps_into=MODELO_100 absent) exercise the error branch. Non-tautological.

### 3. Casilla cross-reference - OK
test_casilla_cross_reference.py scans corpus/casillas/modelo_*/ via pathlib,
calls get_modelo(code), asserts metadata.code.value == code. Guard test
ensures corpus root exists; assert seen prevents silent zero-dir pass.

### 4. Legal citation integrity - OK
Every entry has >=2 LegalCitations (2-4 make_citation calls per file; min 2
on 200/202/232/720/840). make_citation centrally stamps
is_curated_summary=True per ADR section 9 v1 policy. LegalCitation rejects
empty/whitespace quoted_text_es via field_validator.

Spot-checks vs research section 3:
- Modelo 100: LEY 35/2006 art 27 + ORDEN HAC/242/2025 primero. URLs are BOE act.php anchors. Matches research 3.3. OK.
- Modelo 130: RD 439/2007 art 110 + LEY 35/2006 art 99. Trigger notes cite the 70 percent retention rule and mutual exclusivity with 131. OK.
- Modelo 720: RD 1065/2007 art 30 (single primary citation accepted under v1 min_length=1). Gotchas include STJUE C-788/19 and documented corpus-gap marker. Matches research 3.18 + plan Risk table. OK.

### 5. Pydantic v2 discipline - OK
Every model declares ConfigDict(strict=True, frozen=True, extra=forbid).
No dataclasses for boundary types. No bare dict[str, Any] in public signatures.
Two type: ignore[misc] comments narrow Translatable.get() against a TypedDict upstream limitation - acceptable workarounds.

### 6. Enums - OK
ModeloCode, ModeloCategory, ModeloCadence, TaxpayerProfile, LegalCitationSource all enum.StrEnum.
ModeloCode has exactly 20 MODELO_<code> members with three-digit string values.
test_codes enforces count/width/name-value/round-trip.

### 7. Applicability partition - OK
_check_partition enforces pairwise disjointness AND union equals set(TaxpayerProfile).
test_applicability covers happy-path, two-bucket overlap, and missing-profile cases.
_common.build_applicability mechanically computes exempt = all - mandatory - optional.

### 8. Trilingual contract - OK
_display_label_trilingual rejects missing/blank es/en/hu. test_metadata parametrises across all three keys plus blank-value rejection.
Spot-checks on modelos 100, 303, 720 confirm all three languages with authoritative Spanish.

### 9. Typed signatures + Google-style docstrings - OK
get_modelo, modelos_for_profile, year_plan fully typed with Args/Returns/Raises sections.
Package docstring and every public symbol carry Google-style docstrings.

### 10. Public API discipline - OK
__init__.py.__all__ = 15 symbols (alphabetised per plan deviation). Every other file underscore-prefixed.
No external imports from aeat.domain.modelos._*. src/aeat/entrypoints/cli/modelos/__init__.py shim imports aeat.domain.modelos._cli mirroring the existing aeat.entrypoints.cli.deadlines/manual pattern on main.
INFO: ADR section 12 declaration order loosened to alphabetical tuple order per plan-documented deviation. Accepted.

### 11. Errors - OK
ModeloRegistryError(AeatError), UnknownModeloError, RegistryIntegrityError all present.
get_modelo raises UnknownModeloError on coercion failure and lookup miss.
_finalise_registry raises RegistryIntegrityError on every invariant class.
test_error_classes_import asserts subclass relationships.

### 12. Logging - OK
_registry uses aeat.core.logging.get_logger and logs loaded-N-modelo-entries at INFO exactly once at import.
CLI uses typer.echo / rich.Console. Grep for import-logging and print-calls under src/aeat/domain/modelos/ returned zero matches.

### 13. CLI - OK
aeat modelos list/show/applicable-to/year-plan wired into src/aeat/entrypoints/cli/__init__.py alphabetically. Every subcommand carries --json.
year-plan builds AutonomoProfile and calls year_plan(year, profile) which wraps DeadlineEngine(_InProcessCatalogue()).compute(...) honouring the plan DeadlineRule deviation.
test_cli exercises text+JSON for list, --category iva filter, show 303 --json round-trip via model_validate_json, show 999 non-zero, applicable-to autonomo_ed_solo, and year-plan 2026 --tax-id X1234567L --iva-regime GENERAL --json. Zero mocks; real DeadlineEngine exercised.

test_cli uses model_validate_json (not model_validate) because strict pydantic v2 rejects list->frozenset dict coercion - commented in-source.

INFO: _cli.py lines 36-44 reconfigure stdout/stderr to UTF-8 at import time for Windows cp1252. Guarded with contextlib.suppress and idempotent; not a blocker but worth flagging as import-time side-effect for any consumer of aeat.domain.modelos._cli.

### 14. Tests - OK
All new test files colocated under src/aeat/domain/modelos/. Every test module declares pytestmark = pytest.mark.unit.
Zero mock/patch/MagicMock/fake/stub occurrences. test_smoke.py unchanged (15 lines). 756 tests pass.

### 15. No workflow files - OK
.github/workflows/ unchanged from main (only pre-existing ci.yml). test_no_release_please_github_actions_workflow still green.

### 16. Gates - all green (see Gate outcomes above).

### 17. Commit hygiene - OK
Exactly 9 commits, each conventional-commit with (#108) suffix, each matching one plan phase:
- 5b9b3e7 feat(models): scaffold aeat.domain.modelos registry module skeleton
- 1c42e77 feat(models): enums + LegalCitation/Applicability/Metadata
- b2154d3 feat(models): error hierarchy for registry lookups
- 3f3817e feat(models): populate registry with 20 modelo metadata entries
- 74a6362 feat(models): assemble MODELO_REGISTRY with import-time invariant
- bcceb3c test(models): cross-reference casilla catalogue coverage
- b334637 feat(models): CLI subcommands list/show/applicable-to/year-plan
- 0e8fbd2 docs(models): public API docstrings + __all__ lock
- bf9e57b chore(models): lint + typecheck + test green gates

pyproject.toml B008 per-file ignore for _cli.py mirrors the existing src/aeat/entrypoints/cli/**/*.py Typer-defaults ignore; rationale in Phase 9 exec record. No extraneous commits.

### 18. Plan deviations - all accepted
- DeadlineRule field dropped from ModeloMetadata: _metadata.py has no deadline_rule; year_plan resolves at query time via DeadlineEngine.compute. Preserves ADR section 7 intent. ACCEPTED.
- __all__ alphabetised: honoured in __init__.py, contents unchanged. ACCEPTED.
- Modelo 123 caps_into=None with gotcha documenting absent modelo 193. ACCEPTED.
- B008 per-file ignore for _cli.py: honoured in pyproject.toml. ACCEPTED.

### 19. Windows path hygiene - OK
Zero hard-coded backslashes in src/aeat/domain/modelos/. test_casilla_cross_reference uses Path(__file__).resolve().parents[3] / corpus / casillas.
_cli.py reconfigures stdout to UTF-8 explicitly for Windows cp1252. Tests passed on Windows during this review run.

## Deviations from plan / ADR

| Deviation | Documented | Status |
|:--|:--|:--|
| Drop deadline_rule field, resolve at query time | Plan Critical clarification | ACCEPTED |
| __all__ alphabetised | Plan Phase 8 | ACCEPTED |
| Modelo 123 caps_into=None | Plan Phase 4 / Risks | ACCEPTED |
| pyproject.toml B008 per-file ignore for _cli.py | Exec Phase 9 | ACCEPTED |

No undocumented deviations. aeat.domain.deadlines public surface unchanged.

## Verdict

APPROVED - ready for PR.

- Findings: 19 OK, 2 info (CLI stdout-reconfigure import-time side-effect; __all__ alphabetisation), 0 warn, 0 error, 0 blocker.
- All four gates green on Windows (756 passed / 1 skipped / 23 deselected).
- Registry faithfully materialises all 20 modelos; data matches research doc for spot-checked cases (100, 130, 720).
- Every ADR invariant enforced at the earliest sensible phase (import-time where cheap, test-time for casilla cross-ref to avoid dragging aeat.domain.casillas into every consumer).
- The execution agent may open the pull request.
