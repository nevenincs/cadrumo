---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:a17f43cc83652873d63e7cd98d52ef5e02cd06cf4f83d765484710595f906641'
step_id: 'S01'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`

## Description

- Make the unscoped domain resolver `RegistryQueryService._resolve_revision` refuse a non-`None` `as_of` instead of silently ignoring it: raise `RegistryValidationError` naming that the unscoped period query resolves the latest revision by period and has no filing-year context to gate an as_of date, and that a filing-year-scoped query honours as_of.
- Leave the scoped resolver `_resolve_revision_for_scope` unchanged: it already honours `as_of` by passing `on=as_of` into `authority.snapshot` / `select_revision`, which gates the revision against its `valid_from`/`valid_to` window.

## Outcome

The unscoped path stops accepting-and-ignoring `as_of` (the accepted-parameter lie the ADR names) and now refuses explicitly at the single domain choke point every unscoped consumer passes through (`describe_modelo`, `casillas`, `bindings`, `casilla`, `formulas`). `RegistryValidationError` is a `ValueError`, so the CLI discovery handlers' existing `except (ValueError, RegistrySnapshotError)` render it as a clean operator error, not a crash. 21 tests pass in `test_queries.py`; 57 CLI registry integration tests pass; ruff clean; collection clean. The scoped/unscoped distinction the registry-authority-flow decision keeps is preserved — this is an honesty fix, not a merge.

## Notes

git-diff-gated `_queries.py` clean at HEAD before editing (last non-rename touch was the package rename 5 days ago; no peer WIP). No existing test passed as_of to the unscoped path expecting success, so the reject broke nothing. Companion: P01.S02 adds the operator-facing facade refusal, P01.S03 proves both directions.
