---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3f59b53fc041e906bd33fb3ba43aaef8c25b408d6c11ea22355f69e76c403889'
step_id: 'S26'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Settle the reported divergence between the SHA-256 hex length literals and the named constant that states the same length

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/notifications.py`
- `M` `src/cadrumo/application/live/notification_documents.py`
- `M` `src/cadrumo/application/user_profile/custody_transactions.py`
- `M` `src/cadrumo/domain/notifications/__init__.py`
- `verify:` re-censused after the change -- hex-64 shapes still re-declared: 0 (was 6)
- `verify:` canonical probed: 64 lowercase hex accepted; 64 uppercase, 64 non-hex and 63 chars all refused
- `verify:` `pytest domain/notifications + sede -k notification -n 0 -m ""` -> pass (43)

## Notes

`Hex64Str`'s own docstring states the rule this step settles: every hex-64
concept "USES this primitive... It is never re-declared by writing the
``StringConstraints(...)`` call or the pattern out again."

Six fields re-declared it, and NONE of the six carried the pattern. They spelled
`Field(min_length=64, max_length=64)`, which is a length and nothing else, so all
six accepted sixty-four arbitrary characters where the canonical requires
sixty-four lowercase hex digits. The divergence the step reports is therefore not
a stylistic one between a literal and a constant: the re-declarations were
strictly weaker.

Checked each producer before tightening, because uppercase hex is now refused and
a producer emitting it would break:

- both challenge fields come from `secrets.token_hex(32)`, which is lowercase
- the digests come from `sha256_hex(...)` and `hashlib`, also lowercase
- `pdf_sha256` looked like the risk, since a value from the AEAT sede would be
  outside our control. It is not: the field is filled by `sha256_hex(body)` over
  bytes we already hold. A sibling model in the same package already types the
  same field as the canonical, which is what made this one the outlier rather
  than the convention.

Four custody tests fail in this area and none of them touch a hex annotation:
two on an OS keyring the machine cannot write to, one on lock ordering, one on a
peer's retryable-code registry.
