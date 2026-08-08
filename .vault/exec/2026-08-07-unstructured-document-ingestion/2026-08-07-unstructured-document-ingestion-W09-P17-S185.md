---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:988b6dfdab7134737e81210a1ac83952c7b661440f97165fe42dd591b2d9f713'
step_id: 'S185'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Sweep the callers of the country resolver

## Scope

- `src/cadrumo/domain/iva`
- `src/cadrumo/application/ledger`

## Description

- Enumerate every production caller of the country resolver and the structured code resolver outside the defining module.
- Classify each by whether it read the retired shape-based default as decisive evidence.
- Correct the one caller whose refusal prose the narrowing falsified.

## Outcome

Five production callers outside the defining module, and one needed a change.

The classification assembly's territorial resolution described every unresolved stated code as "not a well-formed two-letter country code". Under the narrowing that sentence became false for exactly the population the ruling creates, and it is the sentence an operator acts on: it would have sent them to re-read a field that reads perfectly. It now asks the status axis and says either that the code is reserved to name no country or that the vocabulary does not carry it, with the malformed wording kept for genuinely malformed input.

The remaining four are unaffected and were confirmed rather than assumed. The establishment ladder's country rung is the ruling itself. Its concordant-registration rung resolves a Member State enum member, and every member of that catalogue was re-measured as still resolving. The postal-shape check consults only the printed-name leg, which was already vocabulary-bounded. The evidence draft's resolved-code derivation carries the structured leg's answer, which now declines an unmatched token, and its documented contract already says an uncarried code yields nothing.

No caller was found that had cached or reimplemented the shape default, so nothing was fixed silently.

## Verification

    rg -n "territorial_scope_for_country|country_code_for_stated_country_code" --glob '*.py' --glob '!**/tests/**' --glob '!**/_establishment.py'
    5 production callers across 5 modules, each read in place

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m "unit"
    1699 passed, 22 deselected, 15 warnings in 215.67s (0:03:35)

Every Member State re-measured against the narrowed resolver, confirming the concordant-registration rung is untouched:

    27 members resolve to the Member State scope, Spain alone to no scope

## Notes

A stale comment was found beside the concordant-registration rung and deliberately left: it explains a null return by asserting Northern Ireland is not an ISO jurisdiction the catalogue resolves, while that code has in fact resolved to the Member State scope both before and after this change. The comment predates this work and belongs to a neighbouring lane, so it is reported rather than swept.
