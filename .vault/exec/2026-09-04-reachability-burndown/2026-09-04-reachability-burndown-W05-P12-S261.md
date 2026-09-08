---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:b73efa58523cd7a8a90f7e87aee3a7fd04a47ef40e0b961745584b63e9e70ae9'
step_id: 'S261'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only flow repeat-count mutation in favor of the live answer-driven count owner, and remove the regulatory-cap AST enrollment gate, module/function exemption census, witness registry, and registry-parameterized test that encode production identities as development classifications; retain real domain calculation and flow behavior tests, correct stale prose, run focused gates, remeasure exact reachability and orphan tests, update cadence, and write the Step Record.

## Scope

- `flow engine repeat-count duplicate and tests`
- `regulatory cap enrollment gate and witness census`
- `stale release helper prose`
- `focused domain and flow behavior gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/flows/engine.py`
- `M` `src/cadrumo/application/flows/tests/test_engine.py`
- `D` `src/cadrumo/tests/test_regulatory_cap_term_dominance.py`
- `D` `src/cadrumo/domain/tests/test_regulatory_cap_term_binding.py`
- `D` `src/cadrumo/domain/tests/regulatory_cap_witnesses.py`
- `M` `dev/packaging/tests/_release_cohort_support.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/flows/engine.py src/cadrumo/application/flows/tests/test_engine.py dev/packaging/tests/_release_cohort_support.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/flows/tests/test_engine.py src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_prorrateo.py src/cadrumo/domain/contribuyente/tests/test_deduccion_maternidad_0611.py src/cadrumo/domain/renta/tests/test_maritime_exemption.py src/cadrumo/domain/renta/tests/test_ledger_expenses.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The real flow and tax-domain behavior suites remain green at 148 tests. The first exact pass exposed the duplicate API's private lookup helper, which was removed before closure. The final exact audit has 31 unreachable modules, 284 unused symbols (down from 285), and zero orphaned tests.
