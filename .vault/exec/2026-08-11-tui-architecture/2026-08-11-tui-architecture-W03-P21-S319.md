---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:bfa0dcdd642732da19926b2493460121df2949457925aa447c9dffb4c1355a1f'
step_id: 'S319'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Apply the modelo 347 declaration floor to the RESOLVER-BUILT contraparte rows, which today are emitted unfiltered: `_build_contraparte_clave_rows` groups invoices and emits a row for every country-party-clave combination with no threshold test, so a counterparty whose total operations fall below the RD 1065/2007 art. 31 floor is declared anyway. This is an OVER-declaration live since the clave row family shipped, affecting claves A, B, F and G right now, and it is the direction the codebase does not watch -- the apparatus is built against under-declaration, so an over-declaring path produces valid output, no refusal and no signal. The floor is NOT absent from the codebase, which is why this was easy to miss: `validate_m347_threshold` already refuses operator-supplied rows on the manual detail-row input path, and the summary totals binding applies the floor to its own family; neither reaches the rows the invoice resolver builds. Route the resolver-built rows through the ONE canonical comparison in the m347 threshold module rather than writing a third copy -- that module's own docstring records that the comparison was previously written out separately in each family, byte-identical in two, so mutating one left the other green. Preserve its strict `>` semantics: a counterparty landing exactly on the figure is not declarable. Prove with a grounded case that a below-floor counterparty produces NO row through the real resolver, that an exactly-on-floor counterparty produces none either, and that an above-floor one still does

## Scope

- `the invoice source resolver contraparte row builder`
- `the canonical m347 threshold module as the single comparison home`
- `and a real-resolver threshold proof`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- `_build_contraparte_clave_rows` now pre-filters `observations` to `_m347_declarable_party_ids(observations)` (the SAME helper the summary-totals family already uses, which itself delegates to the canonical `m347_declarable_party_ids` comparison) before grouping into rows, so a counterparty whose total across every clave does not strictly exceed the RD 1065/2007 art. 31 floor produces no row
- `M` `src/cadrumo/domain/calculations/registry/tests/test_contraparte_clave_row_grouping.py` -- bumped two tests' invoice-total fixtures above the floor (200/500/900-euro amounts previously asserted grouping behaviour that the floor now correctly suppresses; the tests' subject is grouping, not the floor, so their fixtures needed to clear it)
- `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py` -- new `test_declaration_floor_gates_the_per_row_family_through_the_real_resolver` (parametrized across both revisions): a below-floor, an exactly-on-floor, and an above-floor counterparty through `resolve_invoice_binding_row_values`, asserting only the above-floor one produces a row; bumped `test_a_quarter_boundary_date_classifies_into_the_correct_quarter`'s fixture amounts (500/700, summing to 1200, below the floor) to 2000/1200 so the quarter-bucketing assertion it exists for still has a row to examine
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy" src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py` -> `pass` (312 passed)

## Notes

Correcting the plan Step's own framing slightly, per the coordinating
session's instruction: the floor was not ABSENT from the codebase, only
absent from the resolver-built row family specifically.
`validate_m347_threshold` already refuses operator-supplied contraparte rows
on the manual detail-row input path, and `_resolve_m347_declarante_summary_values`
already applies the floor to the summary-totals binding family. Both of
those existed before this Step; neither reached the rows
`_build_contraparte_clave_rows` builds. Routed the fix through the SAME
`_m347_declarable_party_ids` helper the summary family already calls (which
itself delegates to the canonical `m347_declarable_party_ids` comparison in
`_m347_threshold.py`), so this is now the third caller of one comparison
rather than a new one -- the exact duplication that module's own docstring
was written to end.

Two pre-existing tests broke as a DIRECT, correct consequence of the fix:
their invoice-total fixtures were below the 3.005,06 EUR floor and their own
subject (grouping, quarter-bucketing) has nothing to do with the floor, so
their fixtures were bumped above it rather than the fix being narrowed to
accommodate them.
