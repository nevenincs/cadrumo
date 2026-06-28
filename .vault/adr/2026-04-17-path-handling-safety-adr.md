---
tags:
  - "#adr"
  - "#path-handling-safety"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-path-handling-safety-research]]"
  - "[[2026-04-17-path-handling-safety-review-audit]]"
---

# `path-handling-safety` adr: `normalize repo-local paths and reject path-like identifiers` | (**status:** `accepted`)

## Problem Statement

Several AEAT subsystems still interpret repo-style paths relative to the process cwd, and several persistence layers allow CLI-supplied ids or persisted relative paths to flow into filesystem joins without containment checks.

## Considerations

- Existing project behavior expects repo-local defaults like `.tokens`, `var/...`, and `corpus/...`.
- The MCP launcher already uses `PROJECT_ROOT` as the anchor for repo-local credential paths.
- Submission, workflow, sync, and manuals loaders all need the same defensive boundary pattern.

## Constraints

- Fixes must preserve current happy-path file locations for normal repo execution.
- Tests must use real filesystem behavior and explicitly cover traversal rejection.
- Scope is limited to path handling safety; no unrelated storage redesign.

## Implementation

- Add shared config helpers that resolve repo-relative path settings against `PROJECT_ROOT`.
- Add a shared path guard for identifier-based JSON records and for persisted relative subpaths.
- Apply the helpers to sync, submission, amendment, workflow, manuals, auth, and doctor surfaces where the audit found path confusion or traversal risk.
- Add negative regression tests for separators, `..`, and root escapes.

## Rationale

The audit found repeated instances of the same bug class. A shared normalization and containment strategy reduces drift and aligns the rest of the codebase with the already-hardened MCP launcher behavior documented in the research and audit.

## Consequences

- Relative paths in `env/.env` become predictably repo-root-relative.
- CLI load/show commands will reject malformed ids earlier.
- Existing tests that assumed unconstrained path joins may need updates, and new negative tests become part of the safety contract.
