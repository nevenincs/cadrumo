---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fbda00b87c6078b6fe02c1d28f986cb4355e4fdb167a270c78005701d1ff8497'
step_id: 'S02'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Remove the divergent fact default from the impatriado income selector so both siblings are required and ## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the divergent fact default from the impatriado income selector so both siblings are required

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py`

## Description

- Remove the divergent `fact` default from `_ImpatriadoLedgerIncomeSelector`.
- Mirror the renta sibling's before-validator so both families refuse an omitted `fact` identically.

## Outcome

Landed in commit `73ea70ea41`, alongside S01.

Both income selectors now require `fact`. This is the half that actually closes the finding: the renta selector defaulted to the cash measure and the impatriado one to the ingresos-integros measure, so one concept carried two silent defaults that disagreed on the figure determining a taxpayer's declared income. Leaving a default on one sibling would have re-created the divergence.

Zero behaviour change: both committed M151 bindings (revisions 2015-y-siguientes and 2025-y-siguientes) declare the ingresos-integros fact explicitly, verified at HEAD.

Test evidence: the impatriado income-binding module passes within the 14-test income-binding run; registry suite counts as recorded in S01.

## Notes

The impatriado default was the STRONGER measure, so removing it changes nothing about correctness on its own. It was removed because a default on one sibling and not the other is exactly the asymmetry that let the divergence survive review.
