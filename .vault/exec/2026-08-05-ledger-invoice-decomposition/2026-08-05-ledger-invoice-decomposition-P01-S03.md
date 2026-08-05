---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:439b7f1c056804b32b37f984942144e0f153aceaf48d604d78c7427165f83381'
step_id: 'S03'
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
     The S03 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched and ## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`

## Description

- Rename the renta and impatriado fact `gross_income_sum` to `cash_received_sum` in the selector literals, the accepted-fact frozensets, the aggregate dispatch, and every docstring naming it.
- Sweep the stale Modelo 130 fragment comment that named the old fact as a live path.
- Leave the Modelo 210 member untouched.

## Outcome

Landed in commit `73ea70ea41`.

The name now states what the code computes: the absolute raw transaction amount, the cash the bank credited. That figure is net of any retencion practicada and possibly IVA-inclusive, so it is neither gross of retencion nor IVA-exclusive - the old name asserted a property the implementation never had, which is why the divergent default survived review. A reader checking the default read a name that sounded correct.

Modelo 210's identically-named member is deliberately NOT renamed: it sums the DECLARED classification amount, not raw cash, so the name is accurate there. Re-verified at HEAD that it is the only committed registry binding using the old spelling, and that it routes through the IRNR selector, a different class.

Registry impact of the rename: zero. No renta or impatriado binding used the member.

## Notes

The rename is a deletion-rename with no alias, per the pre-release no-legacy-compatibility posture.

The M130 fragment comment claiming the operator "selects one binding or the other via the fact selector" was corrected while sweeping: the binding it pointed at is the ingresos-integros one, not a cash-summing path, so the comment named a route that did not exist.
