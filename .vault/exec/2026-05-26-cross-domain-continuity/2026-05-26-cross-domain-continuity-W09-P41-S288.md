---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S288'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S288 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The Close duplicate criterio de caja cash-accounting split and ## Scope

- `model the Ley 37/1992 art 163 quinquies cash-accounting regime`
- `separate from the intracom axes work`
- `out-of-scope for W05.P24 - surface as W09 or future-wave candidate`
- `src/aeat/application/aggregation/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close duplicate criterio de caja cash-accounting split

## Scope

- `model the Ley 37/1992 art 163 quinquies cash-accounting regime`
- `separate from the intracom axes work`
- `out-of-scope for W05.P24 - surface as W09 or future-wave candidate`
- `src/aeat/application/aggregation/`

## Description

- Re-ran the required RAG discovery for criterio de caja/casilla 62 against
  vault records and code.
- Reviewed accepted ADR `2026-07-06-cross-domain-continuity-adr`, S287, and
  S281 execution records.
- Confirmed S281 already landed the cash-accounting regime/payment-evidence
  axis as a non-`IvaCategory` dimension.
- Confirmed the implementation binds the full Modelo 303 cash-accounting
  informational box set, not only the originally mentioned box 62.
- Re-ran focused cash-accounting aggregation and committed-registry tests.

## Outcome

S288 is closed as superseded by S281/S287. No code change was made in this
record.

The original S288 row was opened when casilla 62 was explicitly excluded from
the W05.P24 intracom/export axis work. That split was later resolved by:

- S287: accepted the modelling decision that criterio de caja is an independent
  timing/reporting/payment-evidence axis;
- S281: implemented the axis in transactions, IVA aggregation observations,
  ledger binding selectors, legal catalogue data, and Modelo 303 bindings;
- S281: bound Modelo 303 casillas 62/63 for supplies and 74/75 for acquisitions
  in both committed M303 revision families.

Verification:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_iva_cash_accounting.py src/aeat/domain/calculations/registry/tests/test_modelo_303_cash_accounting.py`
  passed: 4 tests.

## Notes

Residual edge not claimed here: wholly unpaid fallback-only cash-accounting
operations remain intentionally rejected unless payment evidence exists. That
is the S281 contract and prevents silent projection from invoice date alone.
