---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cc30e8e6a7c597581a8ea1f84562deb5978a9fcff7a99a5da9425bfc3a16e835'
step_id: 'S15'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Delete the slim CLI payload schemas and retire the blessing test that creates one invoice in both stores and asserts only that the ids differ, keeping the surviving link tests in that module

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`

## Description

- Delete the slim invoice payload block: the record payload, the shared list result and all five verb envelopes.
- Drop their re-exports from the ledger payloads module and correct its docstring, which still described the deleted family.
- Re-register the canonical payloads on the bare command identifiers the collapsed surface emits.
- Add a registered update envelope carrying the lifecycle event ids.
- Retire the two-store blessing test and repoint the typed-rows assertion onto the canonical list payload.

## Outcome

One payload family serves the invoice noun. Before this, two schemas described one operator concept: slim shapes on the bare command ids, canonical shapes parked under the retired sub-noun ids. Every verb now has exactly one registered output schema.

The blessing test created one invoice in both stores and asserted only that the ids differed. With one store it asserts nothing, and it encoded the split as intended design. The link tests in that module survive.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py -m unit
    20 passed in 19.53s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_lifecycle.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_extract_cli.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_wizard.py -m "unit or integration"
    42 passed in 37.72s

## Notes

The deletion exposed a drift in a neighbouring envelope. The evidence-extract payload had fallen behind the extraction draft and refused four fields it now carries, including the recargo slot -- so a recargo de equivalencia was invisible at the confirm step, which is exactly where an operator is meant to catch it. The envelope was aligned to the draft with typed line and per-rate rows rather than loose mappings.

A second duplication surfaced in the same file and was collapsed: the invoice payload field list was declared twice, and a docstring on one claimed to be the single home for both. The two projections now read one shared field tuple and differ only in wire form, so a field cannot go missing from one surface.
