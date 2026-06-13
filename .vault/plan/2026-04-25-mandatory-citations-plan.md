---
tags:
  - '#plan'
  - '#mandatory-citations'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-mandatory-citations-adr]]"
  - "[[2026-04-25-mandatory-citations-research]]"
  - "[[2026-04-22-citation-blocklist-adr]]"
---

# `mandatory-citations` plan

Implementation plan for issue `#339` — promote "non-empty `legal_basis`
on every `computed=True` casilla" from a convention to an import-time
hard invariant; ship a non-default audit-CLI; lock the convention with
a CI regression guard. Closes the dependency edge for the eleven
Tier-L per-modelo verify-roundtrip issues `#317`-`#327` under EPIC
`#316`. Phase 1 / Phase 2 split avoids a 3-way `cli/__init__.py`
collision with `feature/398` and `feature/399`.

## Proposed Changes

1. **CasillaDefinition validator** — second `@model_validator(mode=
   "after")` on `CasillaDefinition` raising `RulesetValidationError`
   when `computed=True` and `legal_basis == ()`.
2. **No source-enum change** — existing `LegalCitationSource` StrEnum
   already closed; documented via a new explicit unit test.
3. **Audit subpackage** — new `aeat.entrypoints.cli.audit` with
   `validate_citation_coverage` helper, `CitationCoverageReport`
   strict pydantic model, and `aeat audit rulesets citations` Typer
   command. Phase 1 ships subpackage + tests; **does not** modify
   `src/aeat/entrypoints/cli/__init__.py`.
4. **Regression guard** —
   `src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`
   imports `ALL_RULESETS` and asserts 100% coverage on every
   `computed=True` casilla.
5. **Pipeline doc** — `docs/coverage/pipeline.md` cross-cutting row
   for "LegalCitation enforcement".
6. **Phase 2 (deferred)** — single follow-up commit registers
   `audit_app` on the root Typer with `hidden=True`. Lands after
   `#398` or `#399` merges, via a rebase.

## Tasks

- **Phase 1 — Validator + audit subpackage + tests + docs (this PR)**
  1. Add `_require_legal_basis_for_computed` validator on
     `CasillaDefinition` in `src/aeat/domain/formulas/_casilla.py`. Import
     `RulesetValidationError`. Add `# TODO post-#398` marker for the
     future error-code registration.
  2. Add `src/aeat/domain/formulas/test_casilla_validator.py` covering: pass
     case (computed + ≥1 citation), fail case (computed + empty),
     informational-skip case (computed=False + empty).
  3. Add `src/aeat/domain/modelos/test_citations_source_enum.py` covering:
     every `LegalCitationSource` member accepted; freeform string
     rejected.
  4. Create `src/aeat/entrypoints/cli/audit/__init__.py` with `audit_app`,
     `rulesets_app`, and the `citations` command. Reconfigure
     stdout/stderr to UTF-8 at command entry. Add `# TODO post-#399`
     marker for the future `--json` schema.
  5. Create `src/aeat/entrypoints/cli/audit/_helpers.py` with
     `CitationCoverageReport` (frozen + strict pydantic) and
     `validate_citation_coverage(ruleset)` pure function.
  6. Add `src/aeat/entrypoints/cli/audit/test_citations_cmd.py`:
     - happy-path: `CliRunner(audit_app)` invokes `audit rulesets
       citations`; exit 0; output contains every ruleset id;
     - sad-path: build a partial ruleset via `model_construct` with a
       `computed=True` casilla that has empty `legal_basis`; pass it
       through `validate_citation_coverage` directly; assert
       `coverage_percent < 1.0` and `missing_casillas` non-empty;
     - UTF-8 regression: confirm the output stream survives Spanish
       diacritics on Windows-style stdout.
  7. Add
     `src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`
     — imports `ALL_RULESETS`, asserts every ruleset's coverage is
     1.0 on `computed=True` casillas.
  8. Update `docs/coverage/pipeline.md` cross-cutting observables
     table with a "LegalCitation enforcement" row pointing at
     `#339`.
  9. Run `just lint && just typecheck && just test && just hooks` and
     fix any issues at root. Specifically verify: (a) `#338` mutation
     suite green; (b) `#340` integration suite green; (c) coverage
     floor 60% on `src/aeat`.
  10. Write exec records + summary under
      `.vault/exec/2026-04-25-mandatory-citations/`.
  11. Mandatory code review via `vaultspec-code-review`; persist the
      review report under `.vault/audit/`.
  12. Commit + push branch + open PR with `Closes #339`.

- **Phase 2 — Root-Typer registration (deferred, single follow-up
  commit)**
  1. After `#398` (PR `#428`) or `#399` lands on main, rebase
     `chore/339-mandatory-citations` onto fresh main.
  2. Add `from . import audit as audit_module` to
     `src/aeat/entrypoints/cli/__init__.py` and one `app.add_typer(audit_module
     .audit_app, name="audit", hidden=True, help="Audit helpers
     (dev-only).")` line.
  3. Re-run gates; push; merge.

## Parallelization

The Phase 1 work is independent across thread boundaries — no overlap
with `feature/239`, `feature/398`, or `feature/399`'s territory until
the Phase 2 single-line commit. No internal parallelism worth
splitting: validator + audit-CLI + tests should land in one cohesive
commit chain.

Internal commit sequence (recommended):

1. `chore(formulas): mandatory legal_basis validator on computed
   casillas (#339)`
2. `test(formulas): casilla validator + coverage regression (#339)`
3. `test(models): document closed LegalCitationSource catalogue
   (#339)`
4. `feat(cli/audit): add audit rulesets citations CLI (#339)`
5. `test(cli/audit): citations command happy/sad/UTF-8 paths (#339)`
6. `docs(coverage): pipeline.md LegalCitation enforcement row (#339)`

Each commit independently green under the four gates.

## Self-review (against `CLAUDE.md`, project mandates, sibling-branch territory, audit finding)

- ✅ All Python modules under `src/aeat/` — confirmed for new files
  (`src/aeat/entrypoints/cli/audit/__init__.py`, `_helpers.py`,
  `test_citations_cmd.py`; new test modules colocated).
- ✅ Pydantic v2 strict — `CitationCoverageReport` declared
  `frozen=True, strict=True, extra="forbid"`; the new validator on
  `CasillaDefinition` raises (not return-partial-state).
- ✅ No mocks / patches / fakes / stubs — fixture for the audit-CLI
  sad-path uses pydantic's `model_construct` (documented v2 API for
  validator-skipping construction); not a mock or patch.
- ✅ Public API discipline — callers import from `aeat.domain.formulas`,
  `aeat.domain.modelos`, `aeat.entrypoints.cli.audit`. Internal helpers stay
  underscore-prefixed.
- ✅ Errors inherit from `aeat.core.errors.AeatError` — reuses existing
  `RulesetValidationError`.
- ✅ Test markers — every new test module sets `pytestmark =
  [pytest.mark.unit, pytest.mark.domain_submission]` at module level.
- ✅ Trilingual + UTF-8 — audit-CLI reconfigures stdout/stderr to
  UTF-8 at entry; user-facing strings flow through `Translatable` at
  emission with `AEAT_OUTPUT_LANGUAGE` honored.
- ✅ Sibling-branch territory — no edits to `aeat.adapters.outbound.aeat.sede`,
  `aeat.adapters.outbound.aeat.auth._clave_movil`, `aeat.core.errors._registry`,
  `aeat.entrypoints.cli._schemas`, `aeat.entrypoints.cli._exit_codes`, `aeat.entrypoints.cli._tty`,
  `aeat.entrypoints.cli._log_levels`, `aeat.core.logging`.
- ✅ `cli/__init__.py` UNCHANGED in Phase 1 — verified by `git diff
  origin/main..HEAD -- src/aeat/entrypoints/cli/__init__.py` returning empty
  before the Phase 2 step.
- ✅ `#338` + `#340` green — validator merely codifies the existing
  convention; the back-fill sweep confirmed every existing computed
  casilla already cites.
- ✅ Conventional commits — every commit follows the
  `<type>(<scope>): <subject> (#339)` format.
- ✅ `ty` for typecheck (not mypy), `prek` for hooks (not
  pre-commit). No skip directives; root causes only.

**Self-review outcome: PASS.** Plan is consistent with the audit
finding's intent (close the structural gap), respects every project
mandate, and avoids every known sibling-branch collision via the
Phase 1 / Phase 2 split.

## Verification

- All four gates green on Windows: `just lint`, `just typecheck`,
  `just test`, `just hooks`.
- `#338` mutation suite green:
  `just test src/aeat/domain/formulas/_rulesets/test_*_mutation.py
  src/aeat/domain/formulas/_rulesets/test_mutator_exhaustiveness.py
  src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`.
- `#340` integration suite green: `just test
  tests/integration/test_kent_workflows.py`.
- New regression guard green:
  `test_all_rulesets_have_citations.py`.
- Coverage floor 60% on `src/aeat` preserved.
- `git diff origin/main..HEAD -- src/aeat/entrypoints/cli/__init__.py` returns
  empty in Phase 1.
- `aeat.entrypoints.cli.audit.audit_app` is importable; `CliRunner(audit_app)`
  invokes `audit rulesets citations` and renders 100% coverage in
  the happy path.

**Honest assessment of test coverage limits.** The validator is a
pure structural assertion at construction time, exhaustively covered
by unit tests + the regression guard that walks every landed
ruleset. No human-in-the-loop is required for verification in Phase
1. The audit-CLI's stdout rendering is fully exercised via
`CliRunner`. The only Phase-2-deferred surface (the single
`add_typer` line) is mechanical — the eventual rebase will run the
existing CI gates against the registered command.
