---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b569afd55bc9b8b7fc30d61f300374723b3fa6e5bf3d00c52d88d19c63f8ec65'
step_id: 'S27'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Make a re-store of an already-persisted certificado id a content-addressed no-op returning the existing record with no second attachment write and no re-stamped fetched_at, and refuse with an instructive localised conflict when the same certificado id arrives with a different pdf_sha256, verified by an idempotency test covering the no-op, the field-complete match and the divergent-digest refusal

## Scope

- `src/cadrumo/application/live/_notification_documents.py`

## Description

- Look the certificado up before writing anything, and return the record already in custody
  when the incoming document agrees with it.
- Compare every caller-supplied field, not the digest alone, and refuse when any of them
  disagrees.
- Keep identity clock-free: the last-seen timestamp is classified out of the match so a
  retry cannot diverge from itself.
- Refuse in the operator's language, naming the fields that differ, with a real value in all
  four shipped catalogues.
- Rewrite the re-pull test from the rewrite contract to the no-op contract.

## Outcome

A retried pull previously rewrote the row: a fresh attachment write, a re-run of the sancion
reading, a re-stamped timestamp and a second encrypted save, all to produce a record equal
to the one already held. This CLI's operator is an autonomous agent that retries, so that
path ran often and for nothing.

The quieter failure the match guards is more important than the obvious one. A no-op keyed
on the digest alone would accept a retry carrying a new served-from endpoint and discard it
without a word, so the match covers every field the caller supplies. Fields derived from the
document bytes are covered transitively, because the digest that determines them is itself
compared, and re-deriving them would re-run the reading the no-op exists to skip.

A disagreement refuses rather than overwrites. Either the stored row or the incoming one is
wrong about an act AEAT served a taxpayer, and silently replacing one with the other
destroys the evidence of which.

Modified files:

- `src/cadrumo/application/live/_notification_documents.py`
- `src/cadrumo/application/live/tests/test_notification_documents_service.py`
- `src/cadrumo/application/live/tests/test_notification_document_custody.py`
- `src/cadrumo/locales/en.yml`, `src/cadrumo/locales/es.yml`, `src/cadrumo/locales/ca.yml`,
  `src/cadrumo/locales/hu.yml`

That no second lifecycle write occurs is proved against the ciphertext on disk rather than
against the returned value: the secure-object payload is encrypted with a fresh nonce on
every save, so unchanged bytes mean save was never called again. The test carries its own
anti-vacuity proof that the cipher is nondeterministic, without which the comparison would
mean nothing. Removing the existence lookup at runtime reds four of these tests; making the
match compare nothing reds the two refusals.

## Notes

No notice is emitted for the no-op. The service returns a record and carries no notice
channel, and inventing a bespoke advisory field for one call site is the shape the envelope
contract forbids; the caller learns the outcome from the record it receives.

The refusal originally carried an authored message alongside its locale key. A concurrent
change to this package landed a gate forbidding authored refusal text at live raise sites
while this work was in flight, and the raise was adapted to the key-only convention before
landing.
