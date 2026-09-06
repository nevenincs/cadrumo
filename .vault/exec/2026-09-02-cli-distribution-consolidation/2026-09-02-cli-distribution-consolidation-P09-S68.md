---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:292bcba5f40dad9df13732c0ac9d81d8891e31041e751c64f14ac034f4ebbb4d'
step_id: 'S68'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Repair the release automation that had never once completed a release

## Scope

- `release-please-config.json`

## Changes

- `M` `release-please-config.json`
- `M` `.github/workflows/release-please.yml`
- `verify:` `pytest dev/ci/tests/test_action_pinning.py -n0 -m 'unit or integration'` -> `pass`
- `verify:` `release-please tagged v0.5.1 and set autorelease: tagged unaided` -> `pass`
- `verify:` `pypi.org serves cadrumo 0.5.0 and 0.5.1, wheel and sdist` -> `pass`

## Notes

Cadrumo had never completed an automated release. Every run reported SUCCESS
while creating nothing, which is why six months passed without anyone
investigating: a red run gets looked at, a green one that silently did nothing
does not.

Two independent faults in the configuration, both in the same file.
`package-name: cadrumo` set a component the release PR title never carried, so
the merged PR matched zero releases for the path. And
`separate-pull-requests: false` ran the Merge plugin, which aggregates the
single root package into a PR titled `chore: release main` -- carrying no
version, so the release half could not read the version back out of the merged
PR. With no release created, the next run then aborted on the PR its own
predecessor had left untagged: "There are untagged, merged release PRs
outstanding".

The artefacts told the story once read. `v0.4.0`'s tag and GitHub release were
created by hand five hours after PR #670 merged, so the repository had tags
without working automation, and #670 kept the `autorelease: pending` label that
blocked every later run.

Repairs: the component is explicitly empty, matching what the PR carries;
aggregation is off, since one package has nothing to aggregate;
`release-please.yml` also accepts `workflow_dispatch`, because recovering from
a stuck release state previously required inventing a commit.

0.5.0 was completed with a hand-created tag, the state having already been
deadlocked. 0.5.1 was the proof: release-please cut the tag, created the
release, and advanced the label to `autorelease: tagged` with no manual step.

A gate is worth adding and does not exist: a release-please run that finds a
merged untagged release PR and aborts should fail rather than report success.
That green abort is what hid this.
