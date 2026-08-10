---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:3b0dc07f69695b8ad7f0cb5993976f6403421f6a26d9d8d146b4c6840ddfbebf'
step_id: 'S187'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Delete the registration-to-establishment inference

## Scope

- `src/cadrumo/domain/iva`

## Description

- Confirm the sequencing guard before starting: the establishment module was clean at HEAD, so an apply-cached deletion could not be silently reverted by another lane's next working-tree commit of the file. Had it been dirty the row would have been reported blocked rather than started, because reverting the deletion under a commit saying it was disarmed re-arms the footgun invisibly.
- Confirm by reading that the establishment ladder does not reach the function through any indirection, so removing it cannot change a production outcome.
- Delete `territorial_scope_for_printed_tax_identifier` from the establishment module, its module-level export entry, its facade import and its facade export entry, in one index.
- Reword rather than delete the cross-reference in the identification module, which explains why identification and establishment are separate axes and needs the contrast even without the deleted symbol.
- Re-express the two Spanish-identifier assertions onto the identification axis, adding the reason that belongs to that axis: the Spanish prefix is absent from the printed-prefix vocabulary, so a Spanish identification is declared or read from the Spanish identifier authority and never inferred from a printed number.
- Re-express the draft-selection discriminator and STRENGTHEN it rather than restating it.

## Outcome

A public function whose entire semantic was an inference establishment law does not license is gone from the tree. Every Member State registers non-residents, so a printed VAT prefix names identification and never place; the ladder re-runging had already removed the last production caller, but the domain facade kept exporting the inference where any future author could pick it up.

The strengthened discriminator is the part worth recording, because it is where a symbol sweep would have quietly destroyed the test's value. The original asserted that the retired helper WOULD have named a territory for the unselected supplier side while the ladder exhausted — a claim that only exists while the helper does, so a mechanical sweep would have deleted it and left a case passing because nothing asserted anything. It now asserts two things: that the resolved counterparty carries no identification, and that the unselected supplier side names Germany on the identification axis. A resolution that fell through to the wrong party cannot satisfy both.

**What this excludes.** The row's measured scope was exact and fully delivered — nine references, four files, no generated-stub churn, since the module survives and only a function was removed. It does NOT touch the identification axis's own vocabulary: the Spanish prefix remains absent from the printed-prefix vocabulary, which is a separate open row and is the reason the re-expressed assertions read as they do. Nor does it rule on the internal signature names elsewhere in the ladder, which name printed-country parameters while the structured path passes machine-read codes into them; that mislabel is deliberately a different row awaiting a ruling.

## Verification

Landed as one atomic commit across all four files:

    bb681d1022  refactor(iva): drop registration-to-establishment inference
    src/cadrumo/application/ledger/tests/test_establishment_ladder.py  | 19 +++++++-----
    src/cadrumo/domain/iva/__init__.py                                 |  2 --
    src/cadrumo/domain/iva/_establishment.py                           | 22 ------------
    src/cadrumo/domain/iva/_vat_identification.py                      |  5 ++--

Residual-reference sweep after landing, over the whole source and dev trees:

    rg territorial_scope_for_printed_tax_identifier -g '*.py' src dev
    (no matches)

Gate run requested from the single test-run authority rather than executed here.

## Notes

Executed by this lane's Tier-2 worker under the lead's dispatch, so the attribution is this lane's own and the record is authored where the work happened.

The sequencing guard is worth carrying to any similar deletion: a symbol removal staged against HEAD in a file another lane is rewriting is reverted by that lane's next commit of the file, and the revert carries no signal because the deleting commit's message still says the symbol is gone.
