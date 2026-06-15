---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The collapse the near-verbatim invoice and counterpart resolver and validator duplication to one shared implementation parameterised by source kind and ## Scope

- `src/aeat/domain/calculations/registry/_counterpart_bindings.py`
- `src/aeat/domain/calculations/registry/_invoice_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# collapse the near-verbatim invoice and counterpart resolver and validator duplication to one shared implementation parameterised by source kind

## Scope

- `src/aeat/domain/calculations/registry/_counterpart_bindings.py`
- `src/aeat/domain/calculations/registry/_invoice_bindings.py`

## Description

- Extract the two near-verbatim counterpart resolvers into shared `resolve_invoice_family_scalar_values` and `resolve_invoice_family_row_values` cores in `_invoice_bindings.py`, parameterised by source-kind membership set, per-family selector validator, a per-binding observation supplier, and (for rows) a `cohort_by_source` flag; the invoice and counterpart resolvers now both delegate to these cores.
- Collapse the two byte-duplicate `_validate_invoice_fact_and_aggregation` / `_validated_counterpart_selector` bodies into one `validate_invoice_family_fact_and_aggregation` parameterised by `family_label` and a `strict_scalar_shape` flag that toggles the two invoice-only scalar-shape guards the counterpart variant historically omitted.
- Extract the byte-duplicate `intracommunity_clave` field validator and `_validate_rectification` model validator from `InvoiceObservation` and `CounterpartAggregationObservation` into shared `intracommunity_clave_validator` and `validate_rectification_fields` in `_binding_selector_utils.py`.

## Outcome

The invoice/counterpart duplication is collapsed to one shared implementation parameterised by source kind with no behaviour change: the counterpart family preserves its looser scalar-shape behaviour via `strict_scalar_shape=False`, and the counterpart row cohort still keys on `binding.source` via `cohort_by_source=True`. `test_invoice_bindings.py` and `test_counterpart_bindings.py` pass unchanged.

## Notes

`strict_scalar_shape` exactly preserves the prior asymmetry (the counterpart fact/op check never ran the invoice-only "non-row fact must not declare row_field/grouping" / "op rows requires fact row_field" guards). Committed in `refactor(registry): one binding validator contract (W02.P03)`.
