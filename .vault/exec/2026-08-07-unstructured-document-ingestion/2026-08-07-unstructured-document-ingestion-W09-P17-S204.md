---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f312839ea784897c31525cc1864612baa93c7814b7f27436f0c49283d361d48b'
step_id: 'S204'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Close the eight undocumented test-only cross-package private reaches

## Scope

- `src/cadrumo`

## Description

- Promote `ground_extracted_fields` and `parse_invoice_extraction_response` onto the `cadrumo.llm` facade, resolved lazily beside the vision and text readers because the grounding module imports `application.ledger` for the draft shape it returns.
- Promote `write_cached_transcription` onto the `cadrumo.application.ledger` facade lazy export map, matching the sibling extraction-draft writer already exposed there.
- Move the positive-ordinary-tier coverage question into `cadrumo.domain.iva` as `rate_table_covers_any_positive_tier`, beside the table it reads, and delete the application-layer wrapper that duplicated it.
- Add `classifiable_categories` to `cadrumo.domain.iva`, a narrow accessor answering which categories the closed decision table can mint and which of them turn on a given party fact, without publishing the rule rows.
- Relocate the party-fact reporting parity test to `application/invoices/tests`, the package owning the Modelo 349 clave map it primarily asserts about, and give it a second case proving the narrowing is strict so the parity assertion cannot pass vacuously.
- Rewrite four test imports onto facades that already exported the symbol: the registry tree loader, the LLM client, the extraction-draft writer.

## Outcome

All eight reaches are closed at the structure, with zero entries added to the test-debt allowlist. Four were missing facade exports the owning package already published; two were genuine promotions; one was a duplicated predicate deleted in favour of its domain home; one was a misplaced test relocated to the package it asserts about.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py -n0 -q
    19 passed in 121.97s (0:02:01)

    uv run --no-sync pytest -n0 -q -m "(unit or integration) and not external_tool and not os_keychain" <the six touched test files>
    3 failed, 51 passed in 28.81s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m unit
    10 failed, 1769 passed, 21 deselected, 16 warnings in 180.71s (0:03:00)

    uv run --no-sync ruff check src/cadrumo/
    All checks passed!

## Notes

The thirteen failures across the two suite runs are peer surface, not this row's. Three sit in the rate-coverage-versus-legality tests and one in the ledger aggregation suite: all four encode the premise that the Spanish general and reducido rate records begin in 2024, which a peer commit backdated to 2012. Reproduced identically after writing the committed content of both touched files back in place and restoring, so they are unchanged by this row; re-authoring their premise is a tax-grounding judgement belonging to the campaign that moved the rates. The remaining ten are a refused-export-field error across the ledger export actions, touching no symbol this row moved.

The tree-wide type check is red with forty-odd diagnostics spread across peer modules. The two in the ledger facade name a counterparty draft-side symbol declared in `__all__` but not present in the module, which is peer work; every module this row touched is clean under all three checkers.

A sweeper landed most of this work under its own message mid-edit while the suites were running.
