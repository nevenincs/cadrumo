---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:11f6604439b1d84ba38d763b865843062145182376999daf6eb42c393b1cc11b'
step_id: 'S05'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Surface setup-incomplete status in profile listings and the overview calendar

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Description

Executed by a dispatched executor; verified and closed by the
coordinator.

- `ProfilePointerPayload` gains a REQUIRED `status` field, set
  explicitly at both construction sites (list + sandbox) - no silent
  default.
- `config profile list` emits the lifecycle status per row (JSON field
  + text token) and raises a non-blocking info advisory on the typed
  Notice channel when any listed profile is mid-setup.
- The all-profiles overview calendar names each excluded
  setup-incomplete profile on a machine line plus one honesty advisory
  instead of silently dropping it; the ACTIVE-only calendar-build
  filter is preserved (a mid-setup profile is not workable).
- Advisory copy in all four catalogues via the locales CLI.
- New real-behavior CLI suite (3 tests incl. an anti-tautology
  all-active case) staging a real on-disk setup_incomplete manifest.

## Outcome

Commit `d525f645d9` (explicit pathspec, five files). Coordinator
verification: new suite 3/3 under the integration marker; executor ran
the envelope-conformance + sandbox + overview suites (339 passed) and
ruff/format/type checks clean. The two advisory locale keys reached
HEAD swept under the coordinator's `04a09324b3` (concurrent locales-CLI
writes to the shared catalogues); present and parity-clean in all four.

## Notes

Scoping choice ratified: `config profile show` intentionally unchanged
- it already emits the raw status token, and workability belongs to the
readiness verb, so a verdict special-case would duplicate that concern.
Known parallel-run flake: locale parity + audit gates fail under -n
auto and pass sequentially (loader-cache race, per the standing
re-run-before-blaming discipline).
