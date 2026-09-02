---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:11bc17b6736fa38f1f3b44fbf7ee3bf8c23aae38eafdc6edbe5de9642013f750'
step_id: 'S36'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Render the Homebrew formula and the Scoop manifest from the built cohort

## Scope

- `dev/packaging/cohort_manifest.py`

## Changes

- `verify:` `python packaging/scoop/generate.py --cohort-dir var/cohort --version 0.2.2 --release-base-url ... --output ...` -> `pass`
- `verify:` `python packaging/homebrew/generate.py --cohort-dir var/cohort --lock uv.lock --version 0.2.2 --release-base-url ... --output-dir ...` -> `pass`

## Notes

No file in the tree changed: the step proves the two generators produce channel artifacts
from a real cohort, and both do. The Scoop manifest carries the three wheel digests and
the Homebrew formula the source-archive digest, each matching the cohort the builder
sealed at `0.2.2`.

The cohort itself cannot be built in a shared worktree - the builder requires a clean
source snapshot - so it was built in a detached worktree at `107286084c`. The generators
are invoked as scripts rather than modules because the repository root holds a directory
named `packaging`, which the installed distribution of the same name shadows on the
module path; the workflows already invoke them by path for this reason.

Measured on Windows. The Homebrew formula was not audited by `brew`, which needs a macOS
or Linux host.

Two divergences from the target surfaced and are recorded in the research document:
neither channel exposes the second console script, and both source their artifacts from
release assets rather than from the index.
