---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:8d5645ff35fb6dd926cff3c61a0aeb40d6b5d4353efd7a821bd5d240daf283fe'
step_id: 'S18'
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
     The S18 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Re-key the component-expectation table on the category and invoice-kind pair, declaring the retencion role per row so an issued credit and a received liability stop sharing a shape and ## Scope

- `src/cadrumo/domain/iva/_components.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-key the component-expectation table on the category and invoice-kind pair, declaring the retencion role per row so an issued credit and a received liability stop sharing a shape

## Scope

- `src/cadrumo/domain/iva/_components.py`

## Description

- Declare the retención role as a closed set naming whose money a withheld amount is, and validate it against the row's kind so it cannot be authored wrong.
- Declare non-arising (category, kind) pairs as data rather than omitting them, with a mandatory note naming the counterpart category.
- Re-key the Axis-A table on the (category, kind) pair; 36 rows, 18 categories by 2 kinds, none omitted.
- Make the kind a required accessor argument and update the one committed consumer to pass the invoice's own kind.
- Extend the completeness gate to pairs while keeping the category guarantee, and add a non-triviality gate proving the kind axis does real work.

## Outcome

Landed in commit `1e61fc0d74` (4 files, +639/-54).

The retención role is the reason the pair key exists. The same withheld euro is the taxpayer's CREDIT on an invoice they issued - withheld by the payer, deducted from the pago fraccionado under RIRPF art. 110.3.a - and their LIABILITY to AEAT on one they received, where they are the obligated retenedor. Reading the amount without the role turns a deduction into a debt, and category alone cannot carry the distinction.

The role is declared per row so it reads directly, and validated against the row's kind so it cannot be wrong: the builder derives it and the model validator re-checks that derivation, making the two independent statements of one rule rather than one trusted one. A received-side credit is refused at construction.

Non-arising pairs are declared rather than omitted. Omitting them would let the completeness gate be satisfied by narrowing what counts as a valid pair - the gameable form - and would leave a caller holding such an invoice with a lookup failure instead of an answer. A non-arising row must declare every component unknown and name the category that IS this kind's counterpart.

The cuota-less derivation keeps exact parity with the canonical frozenset. Its quantifier is load-bearing: a category is cuota-less only when NO arising kind of it produces a general-303 cuota. Domestic reverse charge carries no cuota issued (the recipient self-assesses) and a real self-assessed one received, so an any-kind reading would declare the whole category cuota-less and silence the advisory on the side that bears one.

Test evidence: domain/iva plus domain/invoices 412 passed, 0 failed (serial). The component-expectation module alone: 58 passed, up from 42.

Each new gate was proven able to fire, by mutation rather than by assertion that it is green:

- Kind-ignoring role derivation: role-coherence gate RED, both-roles-used gate RED.
- Cuota-less quantifier changed from all to any: set-parity gate RED, per-category gate RED.
- Every pair declared arising: non-arising-subset gate RED.

The file was restored after each mutation and the module re-run green (58 passed).

## Notes

NO COMPATIBILITY VIEW, deliberately. A category-only accessor kept alongside the pair-keyed table would have to pick one of the two rows for any category whose sides differ, and would return the wrong one silently on a filing path - worse than the gap this Step closes, and a shim besides. The kind is a required argument instead, and the single committed consumer was updated to pass it.

CROSS-LANE CHANGE, flagged so two exec records do not disagree about who changed what. The invoice decomposition module is owned by the invoice-contracts lane (P03.S13). Two of its call sites took a mechanical signature update to pass the invoice's own kind, which it already held; no design change. It additionally now reports a one-directional category claimed on its impossible side - an import the taxpayer issued, say - as an undeclared IVA treatment rather than reading the wrong row. That lane was offered the alternative of a dedicated defect member instead.

A SECOND CONSUMER COULD NOT BE UPDATED. The withheld-inference work in the income-ledger module calls the same accessor, but that file carries the invoice-contracts lane's live uncommitted WIP and is explicitly not this lane's to touch. Verified that the call does not exist at HEAD - it is entirely working-tree WIP - so this commit leaves HEAD green and only that uncommitted copy needs adapting. The owning lane was notified directly, with the exact one-line change and the reason the issued kind is semantically correct there rather than a placeholder: that path handles incoming actividad receipts against invoices the taxpayer issued, and the kind genuinely matters, since a reverse-charge invoice is zero-cuota issued and cuota-bearing received.

GROUNDING JUDGEMENT ON UNCERTAIN PAIRS. Where the law did not clearly settle whether a pair occurs, the row is declared as arising with an honest note rather than non-arising. The asymmetry is deliberate: a wrongly non-arising pair refuses a real operation, while a wrongly arising one carries an unused row. The régimen simplificado received side is the worked case, and its note states that the pair's existence is itself unsettled.

A pre-existing tension was found and left visible rather than silently resolved: intra-community triangulation is grounded on the acquisition-exemption article, which is a received-side provision, while the shipped row treated it as a non-resident-payer (issued) case. Both sides are now declared, each with the counterparty note its residency implies, and a comment records why a non-arising declaration would have been wrong there.
