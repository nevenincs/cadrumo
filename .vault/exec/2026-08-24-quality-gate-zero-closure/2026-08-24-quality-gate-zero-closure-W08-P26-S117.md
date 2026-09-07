---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:03022b016294956024f650a9dd6150d1a506aa2038f51eb8cc2205b567194f41'
step_id: 'S117'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Re-measure the absence-assertion population at the current revision to scope the work, recording the sampling frame and treating the figure as context rather than as a pass condition, since the 2026-08-04 numbers describe a tree that has moved (Luna max audit)

## Scope

- `.vault/audit/2026-09-07-quality-gate-zero-closure-absence-assertion-current-measurement-audit.md`

## Measurement

- Bound the observation to immutable revision `9e60f9a2b67cf58f5e7455942fc55a9254f8106a` and read `src/cadrumo` from `git archive`, excluding concurrent uncommitted work from the revision-labelled result.
- Parsed 3,804 test modules with zero parse errors.
- Recovered 64 taxonomy vocabulary tokens from the storage-taxonomy declaration source.
- Measured 539 supported absence assertions: 25 inline taxonomy literals, 13 canonical-accessor routes, 107 helper routes, 6 local-variable-held taxonomy literals, 93 unresolved assertions in taxonomy-mentioning modules, and 295 assertions in modules with no taxonomy mention.
- Found 32 live `PINNED_TAXONOMY_LITERALS` declarations and recorded the legacy shrink-only and exception mechanisms that S118 must retire or replace.

## Calibration

The same classifier was run against revision `7ee7ee74411df49ddc57d780c7bf321e6044b792`, the settled 2026-08-04 audit state. It reproduced the earlier partition exactly: 400 total, split 19 inline, 13 accessor-routed, 58 helper-routed, 8 local-variable-held, 89 unresolved taxonomy-mentioning, and 213 token-free.

## Completion boundary

The 539 total and 93 unresolved observations are diagnostic floors and scoping context only. They are not a threshold, baseline, debt allowance, exclusion, or pass condition, and they do not claim complete enumeration. S117 closes when the current immutable measurement and its sampling frame are recorded; S118 owns the bidirectional declaration conformance mechanism.

## Verification

- The measurement probe resolved `HEAD`, archived that exact revision in memory, parsed the declared frame, and completed with a balanced partition and zero parse errors.
- Historical calibration reproduced the source audit's exact six-category partition.
