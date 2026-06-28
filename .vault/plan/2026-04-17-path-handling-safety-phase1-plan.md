---
tags:
  - "#plan"
  - "#path-handling-safety"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-path-handling-safety-adr]]"
  - "[[2026-04-17-path-handling-safety-research]]"
  - "[[2026-04-17-path-handling-safety-review-audit]]"
---

# `path-handling-safety` `phase1` plan

Remediate the audited path-handling defects by normalizing repo-local settings, enforcing containment on persisted relative paths, and rejecting path-like identifiers in file-backed persistence layers.

## Proposed Changes

- Centralize repo-root path normalization in the config layer.
- Centralize safe record-path and relative-subpath resolution.
- Apply the guards to the high-risk sync, submission, amendment, and workflow paths, plus the manuals and credential call sites identified in the audit.
- Add traversal-focused tests to lock in the new boundaries.

## Tasks

- `Normalize config-backed filesystem roots`
- `Harden identifier-to-file persistence loaders`
- `Enforce manuals root containment`
- `Add traversal regression coverage`
- `Verify and append review results to the rolling audit`

## Parallelization

The code changes are tightly coupled through shared helpers, so execution should stay mostly serial. Verification can batch the affected test modules once the implementation stabilizes.

## Verification

- Run targeted unit tests for config, sync, submission, workflow, filing amendments, manuals, and auth/doctor path resolution.
- Run lint on touched Python modules.
- Re-read the rolling audit and confirm every `HIGH` finding is either fixed or explicitly reduced to a lower-risk residual.
