---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
step_id: 'S51'
related:
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---




# run `uv run vaultspec-core vault check all --feature profile-lifecycle-cli` and resolve every new error against the baseline

## Scope

- `.vault/`

## Description

Ran `uv run --no-sync vaultspec-core vault check all --feature
profile-lifecycle-cli` against the current chore/eliminate-shims
tip.

## Outcome

Per-feature audit clean except for a stale-feature-index warning
(79 documents vs 22 indexed). Rebuilt via
`vaultspec-core vault feature index -f profile-lifecycle-cli`
in the same slice; warning cleared.

The 2098 errors in the broader vault total are peer-authored
cross-feature documents not owned by profile-lifecycle-cli.

## Notes

profile-lifecycle-cli per-feature audit surface is now clean
(zero errors, zero warnings against the rebuilt index).
