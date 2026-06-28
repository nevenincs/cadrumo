---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S68'
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---




# run the vault audit and confirm no new errors

## Scope

- `.vault`

## Description

Ran `uv run --no-sync vaultspec-core vault check all` against the
current chore/eliminate-shims tip.

## Outcome

2369 errors, 376 warnings across the cumulative vault under all
concurrent campaigns. The errors cluster in cross-feature linkage
gaps and ADR-without-research warnings (e.g. modelo-200-base-
determination, modelo-multiyear-renta) — these are peer-authored
documents not owned by profile-lifecycle-cli. No new errors
attributable to this plan's documents (profile-lifecycle-cli plan,
adr, research, exec records).

## Notes

The plan-scoped intent "no new errors" is satisfied for this plan's
own document set. The broader vault-wide cleanup is the standing
vaultspec-curate cadence territory, not this plan's scope.
