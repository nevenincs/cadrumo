---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:4e4fa34e67ef34ccdfb81c640fbe2b0db36d54aa4bd4f8673ac30ce04173f9d9'
step_id: 'S37'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Tighten the two surviving duplicate-question pairs by help text: each verb states what it uniquely covers and points at its sibling

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`

## Notes

The two duplicate-question findings were refused as retirements on proof that
each pair does different work, which left the discoverability half unaddressed:
`app registry verify` said "Verify the integrity of the local registry" and
`config repair integrity registry` said "Run full registry validation", so
nothing told an operator which to reach for.

Each of the four verbs now states the thing it uniquely covers and names its
sibling for the rest. This is a tightening rather than a resolution: both pairs
remain live, and the standing goal still asks for one home per question.
