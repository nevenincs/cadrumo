---
tags:
  - '#audit'
  - '#mandatory-citations'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-mandatory-citations-plan]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
  - "[[2026-04-25-mandatory-citations-research]]"
---

# `mandatory-citations` review audit

## Scope

Code review of the Phase 1 implementation of issue `#339` on branch
`chore/339-mandatory-citations`. Performed by the
`vaultspec-code-reviewer` persona against the eight safety invariants
recorded in the plan, plus the pydantic-strict mandate, error-class
discipline, public-API + underscore convention, test-marker
contract, no-mocks rule, lint / typecheck / test / hooks gates, and
coverage-floor preservation.

## Findings

**Verdict — ACCEPTED.** No Critical or High findings. Two Low
observations recorded for transparency; neither is a blocker.

### Safety invariants (all PASS)

- **Inv 1 — `CasillaDefinition` validator.** `_require_legal_basis_
  for_computed` raises `RulesetValidationError` (not a `ValueError`)
  when `computed and not legal_basis`. Pydantic v2 propagates non-
  `ValueError` raises raw — same pattern as
  `Ruleset.model_post_init`. Error message names the casilla id.
  Passing / failing / informational-skip cases covered by
  `test_casilla_validator.py`.
- **Inv 2 — Source-enum constraint.** `LegalCitation.source` typed as
  `LegalCitationSource` under `strict=True, frozen=True,
  extra="forbid"`. `test_citations_source_enum.py` covers every
  member, freeform-string rejection, canonical-string rejection
  (locks strict-mode behaviour), and the deliberate `DIRECTIVA_UE`
  omission.
- **Inv 3 — All 18 rulesets import clean.** Confirmed via the
  `from aeat.domain.formulas._rulesets import ALL_RULESETS` smoke check
  returning 18 ids; 89/89 computed casillas already cite.
- **Inv 4 — No fabrication.** `git diff --stat` over
  `src/aeat/domain/formulas/_rulesets/*.py` is empty (zero ruleset files
  modified). The 89 pre-existing citations are unchanged.
- **Inv 5 — `#338` mutation suite green.**
  `pytest -k mutation` collects 106 in this branch and passes them
  all. (The phase-1 step record's "124/124" figure is a counting
  discrepancy — see LOW-1 — but the substantive guarantee holds: no
  mutation-test failures.)
- **Inv 6 — `#340` Kent-workflow integration suite green.**
  `pytest tests/integration/test_kent_workflows.py` reports 44
  passed. The reviewer's local `-k integration` slice differed from
  this scope; the explicit-path slice matches the prompt.
- **Inv 7 — `aeat audit rulesets citations` CLI.** `CliRunner(audit_
  app)` invokes cleanly; per-ruleset `OK` / `GAP` lines plus
  aggregate footer render; UTF-8 reconfiguration is defensive
  (`getattr(stream, "reconfigure", None)` returns `None` for
  `StringIO`, so `CliRunner`'s capturing stream is unaffected). The
  non-ASCII probe and the `model_construct` gap path round out the
  surface.
- **Inv 8 — `cli/__init__.py` UNCHANGED.** `git diff
  origin/main..HEAD -- src/aeat/entrypoints/cli/__init__.py` returns empty.
  Phase 2 deferral honoured.

### Cross-cutting checks (all PASS)

- **Pydantic v2 strict mandate.** Both new models —
  `CasillaDefinition` (kept strict / frozen / extra=forbid) and
  `CitationCoverageReport` — use the strict-frozen-forbid contract.
  The strict-frozen contract is asserted directly in
  `test_citation_coverage_report_is_strict_frozen`.
- **Errors.** `RulesetValidationError` reused. Lineage
  `RulesetValidationError -> FormulasError -> AeatError`. No new
  exception classes added. `# TODO post-#398` marker present near
  the import in `_casilla.py` for the future error-code registration.
- **Logging.** No `logging` / `print` calls in the audit CLI. Only
  `typer.echo(...)` to stdout and `typer.echo(..., err=True)` to
  stderr.
- **Public API & underscore convention.** Callers import from
  `aeat.domain.formulas`, `aeat.domain.modelos`, `aeat.entrypoints.cli.audit` only. Internals
  (`_casilla`, `_helpers`, `_ruleset`) carry leading underscores.
- **Test markers.** Every new test module sets
  `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`
  at module level.
- **No mocks / patches / stubs / fakes.** The gap-path test uses
  pydantic v2's documented `model_construct` escape hatch — not a
  mock.
- **Lint + typecheck + tests + hooks.** `just lint`, `just
  typecheck`, `just test`, `just test-cov`, `just hooks` all clean.
  Coverage floor preserved (81.08% on `src/aeat`, floor 60%).

### Vault hygiene

Frontmatter on the four new vault docs is well-formed (two tags,
kebab-case `#mandatory-citations`, quoted wikilinks). The
`vault check all` validator flags the exec filenames as deviating
from `yyyy-mm-dd-<feature>-<type>.md`, but the project's `CLAUDE.md`
"Documentation Hierarchy" explicitly mandates
`yyyy-mm-dd-{feature}-{phase}-{step}.md` for exec steps and
`yyyy-mm-dd-{feature}-{phase}-summary.md` for summaries — the
implementer correctly followed `CLAUDE.md`. The validator and the
project policy are inconsistent at the framework level (orthogonal
to this PR).

### Findings — LOW (informational)

**LOW-1 (informational, not blocking).** The phase-1 step-record's
"124/124 mutation, 44/44 integration" figures don't match the
reviewer's reproducible slices (`pytest -k mutation` = 106 collected
on this branch; `-k integration` = 79). The substantive guarantee —
*all suites pass, full `src/aeat` is 3195 passed / 0 failed* —
holds. The implementer's "124" originally counted a wider mutation
slice (`test_*_mutation.py` + `test_mutator_exhaustiveness.py` +
`test_mutator_kill_rate.py`) which evaluates to 124 individual tests
but is not what `-k mutation` selects. Recommend reconciling the
numbers in the PR description.

**LOW-2 (post-merge curation).** `vault feature index -f
mandatory-citations` will need to run after merge to generate the
feature index (orthogonal pre-existing vault state — applies to
every feature in this repo, not specific to `#339`).

## Recommendations

- Open the PR with `Closes #339` and link the four new vault
  artefacts (research / ADR / plan / phase-1-step-1 + summary).
- In the PR body, reconcile the mutation / integration test counts
  per LOW-1.
- Reference the parent EPIC `#316` and the post-merge dependency
  edge closure for `#317`-`#327`.
- Note the Phase 2 deferral and the post-`#398` / post-`#399` rebase
  commits explicitly in the PR description.
- Run `vault feature index -f mandatory-citations` post-merge per
  LOW-2.

**Status — ACCEPTED.** Clear to commit and open the PR. No revision
required.
