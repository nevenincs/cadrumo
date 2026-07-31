---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:a3da50bc64153b43a7422f813e9125bad66482af0092fa3a5775d26fc1e68095'
step_id: 'S09'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Teach the marketplace merge tool to remove a superseded entry and its subtree only where published_by matches this product or is absent, refusing a sibling-owned name identically to a takeover, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes covering own-entry removal, publisher-less removal, sibling refusal, and idempotent re-run on an already-clean index

## Scope

- `dev/packaging/marketplace_publish.py`
- `dev/packaging/tests/`

## Description

- Remove superseded entries during the index merge, under the existing ownership rule.
- Remove the corresponding subtrees, resolving their paths before any mutation.
- Refuse a cohort that both claims and retires one name.
- Prove the sibling bound by mutation.

## Outcome

Landed in the same commit as the declaration it implements.

Removal obeys the ownership rule unchanged. A cohort may retire a name it
published, or one with no recorded publisher, which is exactly the set it could
already claim and overwrite wholesale. A sibling entry is refused. Same bounds,
one more verb, so the guard that exists because a wholesale replacement once
deleted every sibling product is not weakened by a single case.

Retiring subtree paths are resolved from the published index before any
mutation, for the same reason the merge is: the entry names its own path, and
once the index is rewritten that path is gone.

Claiming and superseding one name is refused. The two verbs disagree about what
the resulting tree should hold, and silently preferring either is worse than
stopping.

Gate: the marketplace suite passes at twenty tests, covering the rename, the
sibling refusal, an idempotent replay, the contradiction, and a malformed
declaration.

Anti-tautology proof: letting supersession ignore the ownership rule reds the
sibling-protection test specifically.

## Notes

Idempotence is a requirement rather than a convenience here, because the
declaration ships in every later cohort: a replay must find nothing to retire
and do nothing, while the declaration keeps refusing any later resurrection.
