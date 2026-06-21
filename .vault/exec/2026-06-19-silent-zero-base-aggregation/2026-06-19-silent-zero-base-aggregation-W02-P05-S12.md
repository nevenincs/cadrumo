---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S12'
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
     The S12 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The bind M100 casilla 0171 to the annual income aggregation (project verb uses the formula-runtime path, so no disentanglement needed) with grounded legal_refs (LIRPF art. 27/28) and ## Scope

- `src/aeat/_data/registry/aeat/modelos/100/`
- `src/aeat/_data/registry/aeat/modelos/100/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# bind M100 casilla 0171 to the annual income aggregation (project verb uses the formula-runtime path, so no disentanglement needed) with grounded legal_refs (LIRPF art. 27/28)

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/`
- `src/aeat/_data/registry/aeat/modelos/100/`

## Description

Bound Modelo 100 casilla 0171 "Ingresos de explotación" to the annual income
aggregation, closing its silent zero for direct M100 filings.

- Casilla 0171 set to `input_kind = bound`, `binding = renta-2025-ledger-income-0171`.
- New binding TOML `renta-2025-ledger-income-0171` (source
  `ledger_renta_income_aggregation`, selector modelo=100 target_casilla=0171 fact
  ingresos_integros_sum), grounded in LIRPF art. 27/28 with a source citation.
- Added the binding to the economic-activities construct's binding list.

Files under
`src/aeat/_data/registry/aeat/modelos/100/revisions/2025/` (casillas, bindings,
constructs).

## Outcome

Registry loads; 0171 resolves from the ledger annual income aggregation. No
disentanglement of the project verb was required (it calculates via the
formula-runtime path).

## Notes

None.
