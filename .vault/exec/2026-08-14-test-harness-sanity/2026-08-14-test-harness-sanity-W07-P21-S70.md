---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ea38e66696f8f58a08d6b3d88569eccdaedeb376e197198be170955de4765011'
step_id: 'S70'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Make census drift fail on any unclassified or substitutable duplicate fixture

## Scope

- `dev/quality/tests/test_fixture_census.py`
- `dev/quality/fixture_ownership.py`
- `dev/quality/fixture_ownership.toml`

## Description

- Refuse a manifest that leaves any repeated fixture family without an explicit semantic disposition.
- Refuse a manifest that still declares any substitutable duplicate.
- Refuse any drift between the manifest and the live census, including consumer topology.
- Refuse a bare divergent label over an exact unproven clone, and refuse local consumer-path differences as evidence of divergence.
- Keep the live tree gate in a lane that actually runs it.

## Outcome

The manifest is compared against a freshly generated one for exact equality, so a new, renamed, moved or newly consumed fixture invalidates it rather than passing unnoticed. Unclassified repeated families refuse at generation; declared substitutable duplicates refuse at validation. Decorator spelling, import aliases, helper prose and class placement are all proven insufficient to establish divergence, while a referenced helper's executable value is proven sufficient. The stable writer refuses before replacing bytes, so a refused run leaves the previous manifest intact, and it refuses outright if the source universe changes mid-generation.

## Notes

The gate is complete and its refusals were exercised, but it cannot reach a clean verdict on this worktree, and that is reported rather than worked around. The census is deliberately fail-closed against source mutation during generation, and this tree is shared with several concurrently editing campaigns. One run refused because two source files changed between the before and after snapshots; a later run refused because a manifest record no longer resolves to a fixture body in a file a peer holds open. Both refusals are the instrument behaving correctly. The plan already anticipated that coupling for that file, and the verification phase records the fixture lane as unverifiable here rather than asserting a green it did not observe.

Separately, the disposition vocabulary keys on repeated NAMES, which understates the redundancy it is asked to find. Keying instead on the full constraint shape, name with body digest with scope with autouse, the live tree carries nineteen identical clusters and fifty-four redundant definitions across five hundred and thirty-two fixtures. A name with twenty-six definitions of which eleven are byte-identical is a substantial duplication that a whole-group-identical reading does not surface. The remediation of those clusters is tracked as its own work rather than folded in here, because merging any of them requires preserving scope and autouse exactly: an autouse fixture defined in a module reaches only that module, and the same fixture moved to a package conftest silently reaches every test beside it.
