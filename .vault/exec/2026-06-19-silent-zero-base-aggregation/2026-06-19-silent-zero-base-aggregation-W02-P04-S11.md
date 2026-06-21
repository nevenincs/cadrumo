---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S11'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The admit the annual M100 income target in the renta-income source selector and resolver without disturbing the M130 quarterly path, with the build-validation family case and ## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# admit the annual M100 income target in the renta-income source selector and resolver without disturbing the M130 quarterly path, with the build-validation family case

## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`

## Description

Extended the `ledger_renta_income_aggregation` source to admit the annual M100
income target without disturbing the M130 quarterly path.

- `_RentaLedgerIncomeSelector.modelo` relaxed to `Literal[Modelo.M130, Modelo.M100]`.
- Per-modelo casilla allow-set `_RENTA_INCOME_CASILLAS_BY_MODELO` (M130 -> {01,03},
  M100 -> {0171}); the binding validator checks the target against the selector's
  modelo set.
- Mesh resolver `LedgerRentaIncomeAggregationSourceResolver` routes
  modelo == "100" to the annual aggregator, else the quarterly one.

Files: `src/aeat/domain/calculations/registry/_ledger_bindings.py`,
`src/aeat/application/aggregation/_modelo_bindings.py`.

## Outcome

The build-validation family case and the income binding gates stay green; the
domain resolver folds M100 0171 observations into the live M100 binding (proven by
`test_m100_revision_binds_0171_to_income_source_and_resolves`).

## Notes

The earlier "0171 project-verb collision" concern was disproven: the project verb
uses the formula-runtime path, which tolerates a bound 0171, so no disentanglement
was needed.
