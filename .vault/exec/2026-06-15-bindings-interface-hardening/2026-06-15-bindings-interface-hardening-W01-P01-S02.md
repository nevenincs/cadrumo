---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S02'
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
     The S02 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The replace the ~10 ad-hoc op re-parses with one typed accessor and one declared per-family default, removing the divergent sum-vs-rows silent defaults and ## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# replace the ~10 ad-hoc op re-parses with one typed accessor and one declared per-family default, removing the divergent sum-vs-rows silent defaults

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`

## Description

- Add a single accessor module exposing `binding_aggregation_op(binding) -> BindingAggregationOp`, which returns the binding's explicit typed op or, when absent, the per-family default.
- Declare the per-family default in one place: a `default_binding_aggregation_op(source)` mapping where the four detail-record source kinds (related-party, foreign-asset, atribución, refund) default to rows and every other source folds to sum, removing the divergent sum-vs-rows literal defaults scattered across the re-parse sites.
- Replace every binding op re-parse with the accessor across the previous-filing, counterpart, detail-record, invoice, ledger, and withholding family modules, and the two `op == "rows"` export checks, retyping the helper signatures from raw `str` op to the typed enum.
- Convert the public binding-row projection to emit the op from the typed model rather than a free-form mapping copy.
- Migrate every binding-aggregation reader in the application layer (calc-sheets row collection, row-set assembly lookup) and the test consumers (Modelo 349 declarante/operador binding filters, the cross-dependency contract op-equality assertion, the renta-income/detail-record coverage helpers) from the old Mapping `.get("op")` form onto the typed `.op` accessor.

## Outcome

- All binding op reads flow through one accessor with one declared per-family default; no call site re-parses `aggregation.get("op")` from a free-form mapping or picks a local default.
- The detail-record validators now compare against `BindingAggregationOp.ROWS` and the scalar-folding families against `SUM`/`COUNT_DISTINCT`, with the previous-filing prior-pagos-fraccionados special handling kept explicit.
- The scope fence held: the relation-aggregation re-parses in the relations module and relation-source validator were deliberately left untouched.

## Notes

- The schema retype surfaced eight latent test consumers that constructed a binding aggregation as a raw dict via `model_copy` (which bypasses validation) and then read `.op`. These were the op-mismatch and non-sum rejection fixtures across the counterpart, invoice, ledger-iva, ledger-oss, and registry-schema validator tests. Each was migrated to construct the typed model; the deliberately-invalid `"max"` op fixtures were re-pointed to a valid-but-wrong op (copy) since an unknown op string is now refused at model construction before it can reach the validator under test. These were absorbed as in-scope regressions of the retype.
