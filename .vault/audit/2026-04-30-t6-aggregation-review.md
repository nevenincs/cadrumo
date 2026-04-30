---
tags:
  - '#audit'
  - '#t6-aggregation'
date: '2026-04-30'
related:
  - '[[2026-04-30-t6-aggregation-research]]'
  - '[[2026-04-30-t6-aggregation-adr]]'
  - '[[2026-04-30-t6-aggregation-plan]]'
---

# `t6-aggregation` Code Review

T6-001 | HIGH | Workflow fallback bypassed for Modelo 130 without a transaction catalogue
Reviewer found that workflow default inputs tried the financial provider for supported Modelo 130 even when no persisted transaction catalogue existed, causing empty derived inputs instead of the configured JSON fallback. Resolved by making the financial provider optional in default workflow wiring and using the fallback provider unless the transaction envelope exists. Regression coverage: `src/aeat/cli/workflow/test_cli_runtime.py`.

T6-002 | HIGH | Mixed transactions skipped profile default ratios
Reviewer found that mixed transactions multiplied by `business_pct` but skipped numeric profile proportionality such as the home-office electricity default ratio. Resolved by applying `default_ratio` after fixed percentages regardless of mixed/business classification. Regression coverage: `test_mixed_transaction_multiplies_business_pct_and_profile_ratio`.

T6-003 | MEDIUM | Explicit Modelo 130 mappings accepted computed/result casillas
Reviewer found that any non-`01` mapping was accepted for Modelo 130 expense rows, including computed/result casillas. Resolved by limiting explicit Modelo 130 mappings to the non-computed input casilla set and raising `AggregationCasillaMappingError` otherwise. Regression coverage: `test_modelo_130_refuses_computed_expense_mapping`.

T6-004 | LOW | Human CLI table headers were not trilingual
Reviewer found hard-coded table headers in `aeat financial aggregate` human output. Resolved by routing both table header rows through the nested-dict `Translatable` contract and `AEAT_OUTPUT_LANGUAGE`.

T6-005 | MEDIUM | Import-time storage initialization broke JSON pipe safety
Full coverage revealed that importing the root CLI emitted Alembic plugin logs on stderr because the provider/repository path was imported at CLI startup. Resolved by lazily exposing `FinancialFilingInputsProvider`, lazily constructing workflow financial providers only when the transaction envelope exists, and importing the aggregate command provider only at command execution time. Regression coverage: `src/aeat/cli/test_json_pipe_safety.py`.
