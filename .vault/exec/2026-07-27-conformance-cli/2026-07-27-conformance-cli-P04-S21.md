---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S21'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# wire a conformance recipe invoking python -m dev.registry.conformance report and audit into the task runner

## Scope

- `justfile`

## Description

- Located the Advisory audits section in `justfile` (lines 479-527) — the correct placement block between `audit-health-report-json` and the Documentation section separator.
- Confirmed no peer WIP on `justfile` via `git diff -- justfile` (no output).
- Added `audit-registry-conformance` recipe with a two-line body: `python -m dev.registry.conformance report` then `python -m dev.registry.conformance audit`. Added an inline comment explaining screen posture and directing readers to `audit --check` for gating.
- Committed with explicit pathspec: `0158ac6c3c -- justfile`.

## Outcome

Recipe added and committed. It matches the shape of sibling advisory audit recipes (`@uv run --no-sync python -m dev.XXX`). No logic in the justfile — thin invocation only.

Verified recipe collects correctly:

```
audit-registry-conformance:
    @uv run --no-sync python -m dev.registry.conformance report
    @uv run --no-sync python -m dev.registry.conformance audit
```

Commit SHA: `0158ac6c3c`.

## Notes

The recipe exits 0 always (both `report` and `audit` without `--check` are screen-posture verbs). The gating exit is exclusively in `audit --check`, exercised by the CI integration test added in S19.
