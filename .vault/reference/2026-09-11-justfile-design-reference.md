---
tags:
  - '#reference'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:82a1284a5269d5115e9d2248ede7cc1c5bbd64e44cb6ba4b1d0c618aa0f0fd4d'
related:
  - "[[2026-09-11-justfile-design-adr]]"
  - "[[2026-09-11-justfile-design-plan]]"
  - "[[2026-09-11-justfile-design-research]]"
---

# `justfile-design` reference: `justfile test population and packaging campaign reference`

The implementation is already present in three useful seams: lane transport,
semantic reachability, and the packaging campaign. This reference records the
boundaries that the W03 justfile surface must preserve.

## Summary

`dev/test_runs/lanes.py:82-151` owns subprocess transport, per-lane timing,
continuation after a failure, and the first-failure exit status. It accepts the
lane names from its caller and does not need to know what a lane semantically
contains. `dev/test_runs/paths.py` provides isolated run directories. The
transport boundary is therefore the right place for run-root and report
metadata, but not for test-population membership.

`dev/ci/lane_reachability.py:271-350,905-1094` parses recipes into `Lane`
objects, resolves explicit paths and `--ignore` exclusions, and evaluates
marker expressions structurally. Its `declared_lanes` and `marker_sets_in`
functions are the executable basis for checking that every tracked test has
one canonical owner, while focused selectors and capability exclusions remain
deliberate overlaps or holds-out populations.

`dev/packaging/campaign.py:50-83,177-327,438-664` is the campaign owner. It
keeps profile selection, preflight passes, one Python cohort build, bounded
artifact fan-out, and installed-oracle verification together. The installed
oracle pass and serial passes receive the campaign's exact cohort directory;
justfile recipes should bind them to one cohort-building dependency instead of
rebuilding or reading scratch output independently.

`dev/packaging/python_cohort.py:1-43,903-965` builds a closed, manifest-backed
cohort under `var/`. Its inventory checks reject unexpected files and keep the
cohort immutable for downstream artifact verification. A release aggregate
must not depend on this temporary fixture.

The governing decisions are `justfile-design` and the registry authority /
artifact boundary ADRs listed in the document frontmatter. Their important
divergence from generic CI conventions is that calculation tests remain a
registry-owned population, capability-dependent tests stay outside portable
aggregates, and serial verdicts remain independent from deterministic parallel
verdicts.
