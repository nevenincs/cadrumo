---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b9a6f5d4ac3e7b2df14ef35f2a7949178431ea7789d6e5b9d9ae10e5792e68cd'
step_id: 'S04'
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
     The S04 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker and ## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker

## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py`

## Description

- Declare `LedgerIncomeGrounding` in core as the closed two-member set naming whether an income row's contribution rests on declared invoice substrate or on bank cash.
- Carry it as a required field on `RentaIncomeObservation`, populated at the single classifier construction site.
- Add a model validator refusing a marker that contradicts the declared base it describes.
- Expose the marker on the registry's income observation protocol so the domain screen reads the fact rather than re-deriving nullness.

## Outcome

Landed in commit `bdafb805b3`.

The marker is the fact every consumer keys on. The governing decision is explicit that the advisory, the evidence bundle, and the tests must not each re-derive the distinction from a null base field, and the validator makes the two impossible to drift apart: a row claiming declared substrate while carrying no base is refused at construction, so no downstream consumer has to re-check it.

It lives in core because both the domain registry protocol and the application aggregation pipeline read it, and the domain cannot import the application. That also satisfies the project's closed-value-sets-are-enums-in-core contract.

Test evidence: aggregation plus ledger application suites 1086 passed, 0 failed, 7 deselected (serial). Registry income-binding tests 14 passed, including a new anti-drift test proving a contradicting marker is refused.

## Notes

DIVERGENCE FROM THE STEP AS WRITTEN, deliberate and load-bearing. The Step asks for a "missing-substrate issue reason mirroring the gasto pipeline". The condition was NOT added to the income issue-reason enum.

Every member of that enum EXCLUDES a row - an issue means the row produced no observation. An ungrounded income row is the third outcome class: it still contributes. Recording it as an issue would have misstated the aggregation to every existing consumer of the issues sequence, and the source resolver maps each issue to a source-issue diagnostic meaning "row dropped". The gasto pipeline's member is a true exclusion there, which is why the mirror does not transfer.

The enum docstring now records this explicitly so the next reader does not "fix" the apparent omission. The condition is carried by the grounding marker instead, which is what the same decision asks for in its next sentence.
