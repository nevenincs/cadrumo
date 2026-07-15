---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S01'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Change the configured root package from aeat to cadrumo

## Scope

- `.importlinter`

## Description

- Ground the Step with `vaultspec-rag search "import-linter root package cadrumo architecture contracts" --type code`.
- Confirm the tracked import-linter configuration is the sole live architecture-contract authority.
- Change only the configured root package from `aeat` to `cadrumo`.
- Construct the uncached graph and isolate the contract findings intentionally assigned to later Steps.

## Outcome

The corrected root constructed an uncached graph of 3,421 files and 16,153 dependencies. The four-contract focused run kept the registry, domain-to-application, and domain-to-adapters contracts and exposed the expected helper-mediated break in the core contract. The complete run reached unmatched-ignore validation and reported the two stale censo entries owned by Steps S02 and S03.

## Notes

Semantic search returned the existing layering reporter in `dev/audit/report.py` and the import-linter dependency/configuration references in `pyproject.toml`. Targeted `rg`, `fd`, and `git ls-files` checks found one tracked `.importlinter`; packaging-smoke copies under `var` are generated snapshots, not competing declarations. Duplicate or overlap risk is therefore absent for the root-package authority.

The remaining core chain is `cadrumo.core.tests.test_isolation_fixture_state_root_coverage` through `cadrumo.tests.secure_sql`; Step S04 owns its exact test-only route. No contract, ignore, or ceiling was weakened in this Step.
