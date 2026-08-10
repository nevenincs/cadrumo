---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4ff5b2ab1c60dabe940970f24c75311f0cda2972e6096f3daeb2478504f20fc6'
step_id: 'S297'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# The prefixed-identifier parametrisation: already at HEAD

## Scope

- `src/cadrumo/application/ledger`

## Description

- Read the target case at HEAD before writing the parametrisation, since the file had been edited earlier the same day by another dispatch.
- Find the case already parametrised over both identifier spellings.
- Confirm it drives the ASSEMBLED path rather than the rung, which is the whole point of the row.
- Confirm what it asserts, since a parametrised case that asserts too little would satisfy the letter of the row and none of its purpose.

## Outcome

Nothing was changed. The case is already parametrised over the bare and the prefixed Spanish identifier, drives both spellings through the assembled resolution with a mainland postal code supplied, and asserts that scope, rung, source and declared fact are ALL absent.

That last detail is what makes the existing case sufficient rather than merely present. The row's concern was that a first-decisive-rung reading could go wrong on the prefixed spelling — a Spanish VAT prefix terminating the ladder and yielding a Spanish territory. A case asserting only that the scope is absent would leave that half-open, because a ladder could reach the right answer through the wrong rung. Asserting the rung and the source are also absent pins the path and not just the verdict.

**This row was created by me, this session, splitting a larger row on the ground that this half was agent-actionable while the other half needed an operator ruling.** The split was correct — the two halves genuinely have different owners — but I authored the actionable half without checking whether it was already done, and it was. The split is still worth keeping: the operator half remains genuinely open, and it is now visible as its own row rather than buried inside one recorded as blocked.

**What this excludes.** The composed claim this case pins is that a Spanish prefix plus a fiscal-representative address must not resolve to a Spanish territory. It says nothing about the FOREIGN prefixed forms, which are a different concern and are gated elsewhere.

## Verification

Read directly from HEAD:

    @pytest.mark.parametrize("printed_identifier", [_SPANISH_CIF, f"ES{_SPANISH_CIF}"])
    def test_the_bare_domestic_invoice_exhausts_to_nothing(...)
        application/ledger/tests/test_establishment_ladder.py:298

driving `_resolve` with a mainland postal code and asserting scope, rung, source and declared fact are each absent.

Gate run not requested: no file changed.

## Notes

Executed by this lane's Tier-2 worker under the lead's dispatch, reported as a skip with its evidence.

The lesson is mine rather than the worker's. A row split out of another row inherits the parent's age, and the parent's description of the gap was written when the gap was real. Splitting a row is authoring a row, and it deserves the same premise check any other row gets before dispatch.
