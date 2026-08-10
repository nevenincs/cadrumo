---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:03c564a6ba04d3bf4af7887e94cb72c0d54981e9189eff8c98a62c1f95a80dbb'
step_id: 'S23'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove under-declared Modelo 303 observations are refused and current dispositions round trip

## Scope

- `src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py`

## Description

- Invert the test that asserted an under-declared official payload persists.
- Prove the requirement fires with the opt-in flag NOT passed.
- Prove an unrelated source with the same casillas and no disposition still
  persists and reloads equal.
- Prove a disposition-bearing official payload round trips.
- Assert the repository is unchanged after each refusal.

## Outcome

Landed in `25a22cb` alongside the production change.

The file carried a test asserting that an official Modelo 303 observation with no
disposition IS persisted and reloads equal, refusing only in a downstream
consumer. That test did not miss the defect; it encoded the defect as the
contract, and it is the third such test this campaign has found. Every previous
one was also the defect written down.

It was corrected rather than deleted, and became three tests. Deleting it would
have removed the only coverage protecting the population the refusal is
deliberately scoped away from -- and a refusal with no such control is a refusal
nobody can bound. The surviving control uses an operator-manual source carrying
the same carry casillas and no disposition, and proves it still saves and reloads
equal.

The assertion that decides whether the change is real rather than a rearrangement
is the one exercising the GENERIC path with the opt-in flag defaulted: if that
passes, the hole the row exists for is still open.

## Notes

Both refusal cases assert the observation is absent afterwards, so a refusal that
arrived after a partial write would fail rather than read as success.

The screen runs in the build-only entry point, so no save is reached at all on a
refused payload.
