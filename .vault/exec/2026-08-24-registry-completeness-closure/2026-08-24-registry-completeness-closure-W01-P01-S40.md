---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c5c42871223a3b0cc30071e42e0358920453f78a7721985c925ff4b0d9af9e3e'
step_id: 'S40'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---




# Enforce requested authority grade at the selected-revision snapshot boundary and prove lower-grade escalation refuses

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Compare the law-selected revision's declared authority reach with the caller's requested snapshot grade before any filing-only checks run.
- Refuse every requested grade for an undeclared revision and refuse applicability-to-calculation, applicability-to-filing, and calculation-to-filing escalation.
- Derive grade precedence from `RegistryAuthorityGrade` declaration order rather than maintaining a parallel rank table.
- Exercise the real bundled registry through the snapshot builder and the public `ValidatedRegistryAuthority` facade, including a differential grade mutation.
- Run the focused authority-grade ladder, loader, snapshot-enforcement, and owned-file lint gates.

## Outcome

The selected-revision snapshot boundary is now fail-closed against authority-grade escalation while equal and lower requested grades continue through the existing review, filing-capability, legal, and reference gates. The focused authority-grade suites pass with 31 tests, and `ruff` reports no owned-file findings.

## Notes

No production API or exception type changed. Concurrent edits in peer registry tests and unrelated worktree files were excluded.
