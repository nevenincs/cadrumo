---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0cfe3bdd2e98840eef6cc68fa39982a12a1877ab1100c4bc23483145b53cf456'
step_id: 'S42'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Rewrite the release runbook against the adopted workflow pair

## Scope

- `RELEASING.md`

## Changes

- `M` `RELEASING.md`
- `M` `docs/_release_notes_template.md`
- `M` `dev/packaging/_distribution_limits.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/packaging/tests/test_cadrumo_data_distribution.py dev/packaging/tests/test_distribution_cap.py` -> `pass`

## Notes

The runbook drove `release-orchestrator.yml` as the command that starts a release, eight
times, and that workflow no longer exists. It also described a rehearsal mode, a sealed
candidate namespace, and a close step, none of which the adopted path has. A reader
following it could not have released anything.

It now describes what merging the release pull request actually does, and states two
things an operator would otherwise discover the hard way: the readiness gate blocks on
an evidence set that cannot be satisfied before a first release, and the managed
channels address release assets no workflow produces.

Two consequential corrections came with it. The release-notes template linked to a
`#rollback-procedure` anchor that never existed in the runbook, and the limits module
listed the runbook among the surfaces stating the cap in prose, which it no longer does.
