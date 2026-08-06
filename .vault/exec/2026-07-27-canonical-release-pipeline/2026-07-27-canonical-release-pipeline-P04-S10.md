---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:14632dbcd1a5bf02af90a3fc973402af9a46ed72d44d0636d1111ef25b3b8cb3'
step_id: 'S10'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Add the fail-closed publish preflight refusing while a retired name or retired-identity account metadata remains live and un-superseded in the marketplace index, with the refusal naming the supersession instruction, gate: uv run --no-sync pytest dev/packaging/tests -q -k preflight passes covering the refusal and the clean-pass cases

## Scope

- `dev/packaging/marketplace_publish.py`
- `.github/workflows/publish-release.yml`
- `dev/packaging/tests/`

## Description

- Add a fail-closed verification mode that publishes nothing.
- Refuse a live retired entry, an unreferenced retired tree, and stale metadata.
- Invoke it in the publication path before the merge.
- Prove the orphaned-tree case by mutation.

## Outcome

Landed under the commit subject `feat(packaging): verify the retirement on every
release, not only the one that did it`.

Supersession that is merely performed is a state; supersession that is verified
is an invariant. A performed retirement can be undone by a replay, a stale
manifest, or a stranger claiming the abandoned name, and nothing would notice.
The check therefore re-runs on every release rather than only the one that
retires a name.

Three distinct ways the rename can be half-done are covered. A live retired
entry is the obvious one. A tree with no index entry looks clean in the index and
is still fetchable by direct path, so it continues serving the old identity. And
a marketplace whose plugin list says one name while its description says another
cannot tell a reader which half is authoritative, so metadata retires with the
entries as one event.

Scoped to declared retirements rather than a general scan, so a cohort that
retires nothing is not checked.

Gate: the marketplace and preflight suites pass at fifty-two tests, including the
permit case, since refusals prove nothing without one.

Anti-tautology proof: blinding the check to an orphaned retired tree reds that
case alone, leaving the others green.
