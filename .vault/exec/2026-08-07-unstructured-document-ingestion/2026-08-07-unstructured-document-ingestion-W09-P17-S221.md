---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d346c94ad3a86994ab8b4657c9c7f647460617127485af818526f74fbe4ca3cb'
step_id: 'S221'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Amend the AEAT-register gate's header

## Scope

- `src/cadrumo/domain/iva`

## Description

- Replace the paragraph asserting that no alpha-2-to-alpha-3 authority ships, which the Facturae extract falsified nine minutes after it was written.
- State that membership is grounded and correspondence is not, and cross-reference the sibling gate that grounds it.
- Name why neither gate can close the correspondence: the two enumerations have no overlap.

## Outcome

The header said that nothing in this repository ships an alpha-2-to-alpha-3 correspondence, naming the corpus explicitly, and the Facturae extract landed inside that corpus nine minutes later. A reader auditing coverage would have concluded the Facturae grounding does not exist.

Only half the sentence was stale, and the amendment keeps the half that is true. Ungrounded is now wrong for membership: a sibling gate checks the alpha-3 column against the Facturae CountryType enumeration, which is the authority for what a Facturae document can state and therefore the authority for why the column exists at all. No correspondence ships remains true, and it is the residual the two gates share rather than a gap in either -- this one checks alpha-2 membership against the SII CountryType2, the sibling checks alpha-3 membership against the Facturae CountryType, and the two enumerations have no overlap. Neither can say the three-letter code names the same country as the two-letter one beside it, so a consistent swap of two real pairs survives both. Only the hand-check against AEAT's printed register speaks to that, and it is an attestation rather than a check.

The direction of the error was conservative, which is why it read as harmless and was worth fixing anyway: prose that under-claims a grounding is still prose asserting a property the tree does not have, and the reader it misleads is the one auditing whether the work was done.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_country_codes_against_aeat_register.py src/cadrumo/domain/iva/tests/test_alpha3_against_facturae.py -n0 -q -m unit
    9 passed in 0.99s

Both gates run together deliberately: the amended paragraph now describes the sibling, so a claim about it that had drifted would be visible only by exercising the pair.

## Notes

The staleness was mine and it was created by my own next commit, which is the shape worth noting: the sentence was accurate when written and false within the hour, without either change being wrong. Nothing in the tree would have caught it, because prose describing what does NOT exist has no gate that fails when the thing appears.
