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

# `mandatory-citations` phase-1 summary

Phase 1 of issue `#339` is complete on
`chore/339-mandatory-citations`. The mandatory-citation invariant on
`CasillaDefinition` is enforced at import time; the source-enum
closed-catalogue contract is documented under test; the
`aeat audit rulesets citations` subcommand reports per-modelo coverage
(and exits non-zero on any gap); the parametrised regression guard
walks every landed ruleset; `docs/coverage/pipeline.md` reflects the
new cross-cutting observable. `cli/__init__.py` is unchanged in this
phase, per the agreed Phase 2 deferral.

## Scope landed

- `_require_legal_basis_for_computed` validator on
  `CasillaDefinition` — raises `RulesetValidationError` on
  `computed=True` + empty `legal_basis`.
- `LegalCitationSource` closed-catalogue regression test.
- `aeat.entrypoints.cli.audit` subpackage with `audit_app` + `rulesets_app` +
  `citations_cmd`; pure-function `validate_citation_coverage` and
  `aggregate_reports` helpers; strict + frozen
  `CitationCoverageReport` pydantic model.
- Parametrised regression guard
  (`test_all_rulesets_have_citations.py`) over 18 landed rulesets.
- `docs/coverage/pipeline.md` cross-cutting row.
- Two pre-existing test files
  (`src/aeat/domain/formulas/test_engine.py` and
  `src/aeat/domain/formulas/test_ruleset.py`) updated with fixture citations
  so their synthetic computed casillas satisfy the new validator.

## Back-fill inventory (per safety invariant 4)

Pre-implementation sweep returned **zero** gaps across all 18 landed
rulesets (89 / 89 computed casillas already cite). No
`citation-pending` follow-up issues filed; per-modelo detail recorded
in the step-1 record.

## Source-enum constraint impact (per safety invariant 2)

The existing `LegalCitationSource` StrEnum already enforced the
closed-catalogue contract. No source-code change. The regression test
locks the 6-member catalogue and documents the `DIRECTIVA_UE`
deferral. No existing citations needed normalisation.

## Gate status (per safety invariant 5/6/7/8)

- `just lint` ✅
- `just typecheck` ✅
- `just test` ✅ — 3195 passed
- `just test-cov` ✅ — 81.08% (floor 60%)
- `just hooks` ✅ — every prek hook clean
- `#338` mutation suite ✅ — 124 / 124 passed
- `#340` Kent-workflow integration suite ✅ — 44 / 44 passed
- `aeat audit rulesets citations` exits 0 (every ruleset 100%
  covered); UTF-8 safe on Windows
- `git diff origin/main..HEAD -- src/aeat/entrypoints/cli/__init__.py` returns
  empty (Phase 1 invariant)

## Phase 2 deferred work

- One-line `app.add_typer(audit_module.audit_app, name="audit",
  help="Audit helpers (dev-only).", hidden=True)` registration on
  the root `aeat` Typer plus the matching import. Lands as a single
  follow-up commit after `#398` (PR `#428`) or `#399` merges, via a
  rebase.
- Post-`#398` rebase additionally registers an `ErrorCode` for
  `RulesetValidationError` under `INTEGRITY` (TODO marker present in
  `src/aeat/domain/formulas/_casilla.py`).
- Post-`#399` rebase wires the `--json` `OutputSchema` for the audit
  CLI (TODO marker present in `src/aeat/entrypoints/cli/audit/_helpers.py`).

## EPIC-level consequence

Closes the dependency edge for `#317`-`#327` (eleven Tier-L per-modelo
verify-roundtrip issues): each per-modelo issue starts from a
baseline where every computed casilla is provably traceable to a BOE
primary source via the import-time invariant + the audit reporter.
