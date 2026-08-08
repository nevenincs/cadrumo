---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ca595df4dbc21edeb4a307aa4792bb5935944673e0617396b0a6ee0b34b4b093'
step_id: 'S238'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# REWRITTEN. The original premise was void: the German fixture confirms at HEAD unmodified, and the refusal that prompted this row was a correct refusal of a wrong input, since evidence confirm's --country-code is required and names the COUNTERPARTY's country while ES was supplied for a Swedish supplier. The line originally blamed cannot produce that symptom either, because it returns None on a failed checksum rather than raising. The real defect is narrow: canonical_identity_token picks its validator from the ADDRESS country while the identifier's own PREFIX already answers, and the invoice normaliser documents that exact rule in its own comment, that the source is the printed VAT number's own prefix and nothing else and the country beside it is an address deliberately not consulted. So the authority exists and this site disagrees with it. Measured: the Swedish identifier yields None by address while its prefix reads se, and an ES-prefixed Spanish one already strips correctly, so the site handles one prefix and ignores every other. BLOCKING GATE on the fix: reachability is unproven rather than proven-nil, since the structured reader takes the identifier from the record and never reaches this call, and the text and semantic reading paths cannot be exercised on this box for want of an on-host model. Require a caller measured to reach it with a non-None foreign identifier before claiming the fix is felt

## Scope

- `src/cadrumo/application/ledger`

## Description

- Ask the identifier's own prefix before assuming Spain when canonicalising a printed tax identifier with no stated country, routing through the single authority on which country a printed number names rather than adding a second rule set.
- Keep a supplied country decisive, so only the absence position moves.
- Correct the docstring on the establishment-key derivation, whose rationale covered an unprefixed foreign number and was silent on a prefixed one.
- Correct the regression that named the no-prefix property while passing an identifier that carries its prefix, and add the paired positive case through a real store round trip.

## Outcome

The row's original premise was void and was rewritten before this work started: the fixture that prompted it confirms at HEAD unmodified, and the refusal that looked like a defect was a correct refusal of a wrong input. The line originally blamed cannot raise at all. What survived is narrow and real.

The blocking reachability gate was satisfied by measurement rather than argument, and satisfying it changed the finding. Instrumenting the call from outside the repository across a real lane recorded 226 calls, 16 carrying an identifier whose prefix names a foreign country, 13 of those yielding no verdict. Capturing the production frames -- not only the arguments -- showed all 13 reaching through production code and identified the starved consumer, which argument-level reachability could not have done.

That consumer is the establishment-record key, not the unverified-identifier finding anyone expected. The key is the digest of the canonical identifier and it is the address of a counterparty's stored establishment fact, so no verdict meant no key, and no key meant no confirmed fact could be stored for that counterparty and none retrieved. The remembered-fact rung was therefore unreachable for the entire foreign-counterparty population -- precisely the population the intra-community and export treatment exists for. The once-per-counterparty loop could never have closed for them.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m unit
    1945 passed, 26 deselected, 16 warnings in 270.64s (0:04:30)

Four positions measured directly, showing only the absence position moved: an unqualified foreign number now canonicalises where it previously did not; the same number under a supplied Spanish country still refuses; a bare Spanish identifier is unchanged; a body with no prefix still yields nothing.

End to end through the real CLI, the counterparty confirm verb now records a fact for a foreign identifier and the subsequent document confirm no longer raises the counterparty establishment question, leaving only the filer's own profile gap. Before the change that verb refused outright.

Mutation proof, run from outside the repository with three rungs asserted -- the rebinding found a holder, the holder was replaced, and the observable token flipped -- reds exactly the new behaviour gate and nothing else: 1 failed, 21 passed.

## Notes

The regression that named this property asserted it against an identifier carrying its prefix while its own message described a number without one, so it locked in the default it read as protecting against. It was corrected rather than deleted, and the property it meant to hold is now gated on a value that actually lacks a prefix.

The rationale on the key derivation was true and narrower than the behaviour it justified: correct about an unprefixed foreign number, silent on a prefixed one. That shape reads as a considered decision, which is why it survived, and it is worth watching for wherever a default carries its justification in prose.

Code review has not yet run against this change.
