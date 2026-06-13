---
tags:
  - "#exec"
  - "#t6-aggregation"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-t6-aggregation-plan]]"
  - "[[2026-04-30-t6-aggregation-adr]]"
---

# t6-aggregation CLI and provider execution

Implemented the public command and workflow input bridge:

- Added `FinancialFilingInputsProvider`, conforming to the existing workflow inputs provider protocol by returning `Mapping[str, Decimal]`.
- Added `FinancialThenJsonInputsProvider` so workflow derivation uses the financial catalogue for supported modelos and falls back to JSON for unsupported modelos.
- Registered `aeat financial aggregate --modelo <code> --period <period> [--json]`.
- Registered the `financial aggregate` JSON schema as `OutputRootSchema[CasillaAggregation]`.
- Registered aggregation error codes in `aeat.core.errors._registry`.

Verification:

- `test_cli_aggregate_json_round_trips`
- `src/aeat/entrypoints/cli/test_json_schema_conformance.py`
- `src/aeat/core/errors/test_registry.py`
- `src/aeat/core/errors/test_registry_enforcement.py`
