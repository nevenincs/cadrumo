---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6098dacb1c2a64a20ac86a5412455d929bc340989e7aad7fd590e121b98eb7b5'
step_id: 'S03'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove current profile schema hydration and non-current marker refusal

## Scope

- `src/cadrumo/domain/user_profile/tests/test_payload_schema_identity.py`

## Description

- Delete the test asserting the version is bounded above rather than pinned.
- Add pre-current refusal for the live record and for the immutable snapshot.
- Add a proof that a defaulted record now carries the canonical version.
- Add a proof that the current schema hydrates through the snapshot.

## Outcome

Landed in `b409fa2`, the same commit as the production change it guards, because
they are one contract and splitting them would have left a window where the
suite asserted the opposite of the code.

The file carried a test named for being bounded above and not pinned, whose body
asserted that a defaulted record's version was strictly LESS than the canonical
one, with a docstring explaining that pinning would refuse the records this
codebase writes. That test did not merely fail to catch the defect; it encoded
the defect as the contract, which is worse than having no test, and it would have
reddened on any correct fix. It was corrected rather than renamed, marked or
allowlisted.

The added refusals reuse the existing payload helper that re-derives the
canonical hash over the overridden metadata. Without that step a mutated payload
also breaks its own digest, and the resulting refusal proves the hash check
rather than the schema guard -- a passing test that measures the wrong thing.

Nine tests now cover unknown id, future version, pre-current version and
canonical acceptance across both the record and the snapshot.

## Notes

No mocks, no monkeypatching of the schema loader, no fabricated schema object;
the real loader runs. Verified at HEAD independently rather than on the
implementer's report.
