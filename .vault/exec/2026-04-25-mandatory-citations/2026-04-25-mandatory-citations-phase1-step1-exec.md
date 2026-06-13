---
tags:
  - '#exec'
  - '#mandatory-citations'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-mandatory-citations-plan]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
  - "[[2026-04-25-mandatory-citations-research]]"
---

# `mandatory-citations` phase-1 step-1: validator + audit CLI

Phase 1 of issue `#339`: ship the mandatory-citation invariant on
`CasillaDefinition`, the closed-catalogue regression test for
`LegalCitationSource`, the `aeat audit rulesets citations` subcommand
surface, and the parametrised regression guard over every landed
ruleset. `cli/__init__.py` is intentionally **not** modified — Phase 2
deferral.

## Files modified

- `src/aeat/domain/formulas/_casilla.py` — added
  `_require_legal_basis_for_computed` `@model_validator(mode="after")`
  raising `RulesetValidationError` on `computed=True` + empty
  `legal_basis`. Imported `RulesetValidationError` from `aeat.core.errors`.
  Added a `# TODO post-#398` marker for the future error-code
  registration.
- `src/aeat/domain/formulas/test_engine.py` — added a `LegalCitation` fixture
  to the synthetic ruleset built inside
  `test_derive_division_by_zero_raises_evaluation_error` so its
  `computed=True` casilla satisfies the new validator.
- `src/aeat/domain/formulas/test_ruleset.py` — added a module-level
  `_FIXTURE_CITATION` and propagated it through `_make_casilla` so the
  three structural-invariant tests build computed casillas with a
  citation.
- `docs/coverage/pipeline.md` — added a "Mandatory `LegalCitation` on
  every `computed=True` casilla" cross-cutting row pointing at `#339`.

## Files created

- `src/aeat/entrypoints/cli/audit/__init__.py` — `audit_app` + `rulesets_app` +
  `citations_cmd` Typer surface; `_reconfigure_utf8` helper guarding
  the Windows cp1252 path; renders one line per ruleset + an
  aggregate; exits non-zero on any gap.
- `src/aeat/entrypoints/cli/audit/_helpers.py` — `CitationCoverageReport`
  (frozen+strict pydantic v2), `validate_citation_coverage(ruleset)`
  pure function, `aggregate_reports(reports)` flattener. Includes a
  `# TODO post-#399` marker for the future `--json` schema registration.
- `src/aeat/entrypoints/cli/audit/test_citations_cmd.py` — six tests covering
  happy path, UTF-8-safety probe, simulated-gap path via
  `model_construct`, zero-computed edge case, frozen-model contract
  assertion, and aggregate missing-casilla flattening.
- `src/aeat/domain/formulas/test_casilla_validator.py` — four unit tests for
  the validator: pass case, fail case, informational-skip case,
  multiple-citation pass case.
- `src/aeat/domain/modelos/test_citations_source_enum.py` — four tests
  documenting the closed-enum behaviour, the strict-mode rejection of
  string canonical values, and the deliberate omission of
  `DIRECTIVA_UE`.
- `src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py` —
  parametrised regression guard over `ALL_RULESETS` (18 rulesets +
  one "no formulaless shell" sanity test).

## Description

The validator on `CasillaDefinition` is the structural change at the
heart of issue `#339`. It runs at construction time via pydantic v2's
`@model_validator(mode="after")`, raising `RulesetValidationError`
(which inherits `FormulasError -> AeatError`) when a `computed=True`
casilla has empty `legal_basis`. Pydantic v2 propagates non-`ValueError`
exceptions raw, matching the established pattern on
`Ruleset.model_post_init`.

The closed-catalogue test on `LegalCitationSource` confirms two
properties: every member of the existing 6-element StrEnum is
accepted; freeform / canonical-value strings are refused under the
model's `strict=True` config. The handover prompt's proposed
`DIRECTIVA_UE` member is documented as a deferred extension — zero
landed rulesets cite an EU directive directly.

The `aeat audit rulesets citations` subcommand provides a defence-in-
depth audit surface. The validator already prevents any real ruleset
from shipping a gap; the audit CLI exists to (a) report coverage in a
human-readable form, (b) serve as the EPIC `#316` per-modelo
verify-roundtrip baseline-reporter, (c) survive the inevitable Windows
cp1252 + Spanish-diacritic regression by reconfiguring stdout/stderr
to UTF-8 at command entry. The subpackage is fully importable in
isolation via `from aeat.entrypoints.cli.audit import audit_app;
CliRunner(audit_app)`. Phase 2 will add the single-line registration
on the root `aeat` Typer.

## Back-fill inventory

A pre-implementation sweep at `chore/339-mandatory-citations` HEAD
(post-`dae0ff2`) confirmed **zero** back-fill volume: all 89
`computed=True` casillas across the 18 landed rulesets already carry
non-empty `legal_basis`. The validator codifies an existing
convention; no `citation-pending` follow-up issues are filed.

| ruleset_id              | total computed | with citation | gaps |
|-------------------------|---------------:|--------------:|-----:|
| modelo_100.summary.2025 |              4 |             4 |    0 |
| modelo_111.2024         |              4 |             4 |    0 |
| modelo_111.2025         |              4 |             4 |    0 |
| modelo_115.2024         |              2 |             2 |    0 |
| modelo_115.2025         |              2 |             2 |    0 |
| modelo_123.2024         |              4 |             4 |    0 |
| modelo_123.2025         |              4 |             4 |    0 |
| modelo_130.2024         |              9 |             9 |    0 |
| modelo_130.2025         |              9 |             9 |    0 |
| modelo_131.2024         |              6 |             6 |    0 |
| modelo_131.2025         |              6 |             6 |    0 |
| modelo_180.2024         |              1 |             1 |    0 |
| modelo_180.2025         |              1 |             1 |    0 |
| modelo_200.2024         |              3 |             3 |    0 |
| modelo_202.2025         |              3 |             3 |    0 |
| modelo_303.2024         |             12 |            12 |    0 |
| modelo_303.2025         |             12 |            12 |    0 |
| modelo_390.2025         |              3 |             3 |    0 |
| **total**               |         **89** |        **89** |**0** |

## Tests

- `src/aeat/domain/formulas/test_casilla_validator.py` — 4 / 4 passed.
- `src/aeat/domain/modelos/test_citations_source_enum.py` — 4 / 4 passed.
- `src/aeat/entrypoints/cli/audit/test_citations_cmd.py` — 6 / 6 passed.
- `src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`
  — 19 / 19 passed (one parametrise per ruleset + the no-shell
  sanity test).
- `#338` mutation suite — 124 / 124 passed.
- `#340` Kent-workflow integration suite — 44 / 44 passed.
- Full pytest suite — 3195 / 3195 passed; 13 skipped; 24 deselected.
- Coverage gate — 81.08% on `src/aeat`, well above the 60% floor.

## Gates

- `just lint` — clean.
- `just typecheck` — clean.
- `just test` — 3195 passed.
- `just test-cov` — 81.08% (floor 60%).
- `just hooks` — every prek hook clean (ruff format applied a single
  reformat pass to the new test fixtures; tracked in this commit).
- `git diff origin/main..HEAD -- src/aeat/entrypoints/cli/__init__.py` — empty
  (Phase 1 invariant verified).
