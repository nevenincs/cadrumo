---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:905277387dce35a059eebfa9b0e6b5137f37eddfd544226f78359a2f11eefcdd'
step_id: 'S304'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop modelo 347 silently deleting every non-resident counterparty from the declaration: the invoice observation builder refuses any invoice whose counterparty country is not ES and returns nothing, with no comment or citation beside it while the adjacent tax-id skip carries its governing article, so a filer's above-threshold operation with a foreign counterparty is absent from the file with no refusal and no advisory; RD 1065/2007 art. 33.2's exhaustive exclusion list contains no counterparty-residency exclusion, excluding only the filer's own foreign permanent establishment and operations already reported through a coincident informativa, and the diseño's own country slot exists for exactly the non-established non-resident the gate deletes; remove the residency filter, keep only the exclusions the article actually names, and prove an ordinary non-recapitulativa operation with a non-resident counterparty reaches the declaration while an intra-community one still routes to its own informativa

## Scope

- `the modelo 347 invoice observation builder in application/invoices/_source_resolver.py`
- `the capability-parity test whose fixture varies counterparty country only together with an intra-community category`
- `and a grounded non-resident counterparty inclusion test`

## Changes

- `A` `.vault/adr/2026-08-27-tui-architecture-modelo-347-counterparty-residency-scope-adr.md`
- `A` `.vault/audit/2026-08-27-tui-architecture-modelo-347-nonresident-counterparty-silent-exclusion-audit.md`
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- `_m347_invoice_observation` drops the `counterparty_country != "ES"` filter; excludes only via `_intracommunity_clave(invoice) is not None` (RD 1065/2007 art. 33.2.i)
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- renamed and re-documented `test_capability_parity_m347_declares_only_the_domestic_party` to `..._excludes_the_intracommunity_operations`; added `test_m347_declares_an_ordinary_operation_with_a_nonresident_counterparty`
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -q -k "347"` -> `pass` (3 passed)

## Notes

Built in the SAME change as S302 (the resolver gate and the `pais-codigo` per-row
source are interdependent per the ADR's own Consequences section: opening the
gate alone would render non-resident rows with an incomplete mandatory field).
See `2026-08-11-tui-architecture-W03-P21-S302.md` for the export-field-split
half of this combined change and its shared verification run.
