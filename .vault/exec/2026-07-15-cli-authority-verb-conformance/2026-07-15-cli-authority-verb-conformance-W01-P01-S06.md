---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S06'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the concrete transaction-repository fallback and require TransactionCatalogueRepositoryProtocol

## Scope

- `src/cadrumo/application/aggregation/_irnr_income_ledger.py`

## Description

- Ground the Step with `vaultspec-rag search "IRNR income ledger injected transaction repository remove ambient fallback" --type code`.
- Confirm the complete exact graph with targeted searches for `aggregate_irnr_income_ledger_from_repositories` and `LedgerIrnrIncomeAggregationSourceResolver`.
- Remove the concrete persistence-adapter import from `src/cadrumo/application/aggregation/_irnr_income_ledger.py`.
- Require an injected `TransactionCatalogueRepositoryProtocol` and remove the ambient concrete-repository fallback.
- Preserve bucket-identity validation, date partitioning, typed aggregation issues, and result construction unchanged.
- Run focused Ruff and the real encrypted-repository Modelo 210 aggregation suite.

## Outcome

`aggregate_irnr_income_ledger_from_repositories` now has one repository authority: its caller must inject the domain Protocol. The function can no longer construct a concrete persistence adapter from ambient runtime state, closing its half of the duplicate composition door without adding an import-linter ignore or compatibility default.

The exact caller inventory contains one production call in `src/cadrumo/application/aggregation/_modelo_bindings.py` and two direct real-repository calls in `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`; all three already pass a repository argument. The sole production `LedgerIrnrIncomeAggregationSourceResolver` construction in `src/cadrumo/application/modelo/_calculation_actions.py` already receives the source mesh's memoized repository.

Verification passed:

- `uv run --no-sync ruff check src/cadrumo/application/aggregation/_irnr_income_ledger.py src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py` reported `All checks passed!`.
- `uv run --no-sync pytest -q src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py` reported `2 passed in 53.44s`.
- `vault plan check` reported no findings after closing only S06 through the canonical plan command.
- `vault check adr-status` reported clean; `vault check schema` reported only the pre-existing unrelated missing-research warning for `2026-07-14-honest-all-green-plan.md`.

## Notes

The mandatory semantic query did not return the IRNR aggregation epicenter; its highest-ranked result was the separate verification-time transaction fallback in `src/cadrumo/application/modelo/_verification_actions.py`. Targeted symbol search therefore supplied the authoritative graph, and the index miss is recorded rather than treated as positive evidence.

Step S07 remains required: the public `LedgerIrnrIncomeAggregationSourceResolver` constructor still accepts an optional repository and must be changed to require `TransactionCatalogueRepositoryProtocol`. This Step deliberately did not edit `src/cadrumo/application/aggregation/_modelo_bindings.py` or the peer-dirty `src/cadrumo/application/modelo/_calculation_actions.py`.

No destructive worktree command, compatibility path, test double, skip, or unrelated cleanup was used.

Focused `vaultspec-code-reviewer` safety, intent, boundary, and quality review status: PASS, with zero critical or high findings. The required S07 constructor change is a planned next-Step dependency, not an undocumented compatibility path in S06.

Feature-index regeneration succeeded. Its repository-wide discovery emitted pre-existing stem-collision warnings for unrelated historical execution records; the generated feature index includes the S06 record and required campaign documents.
