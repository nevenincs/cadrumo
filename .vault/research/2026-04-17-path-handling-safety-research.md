---
tags:
  - "#research"
  - "#path-handling-safety"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-path-handling-safety-review-audit]]"
---

# `path-handling-safety` research

## Scope

Review path handling across config-derived filesystem roots, persisted relative paths, and CLI-exposed record identifiers.

## Findings

- Multiple persistence layers derive filenames directly from unconstrained ids.
- Several path-valued settings loaded from `env/.env` remain cwd-relative at runtime.
- Manuals corpus loaders trust persisted relative paths without enforcing root containment.
- The recent MCP shim already established the desired repo-root-relative credential resolution pattern.

## Recommendation

- Introduce one shared config path-normalization helper so repo-relative settings resolve against `PROJECT_ROOT`.
- Introduce one shared identifier/path containment helper for persistence layers and corpus loaders.
- Harden every CLI-exposed load path that turns ids into filenames.
- Add traversal-focused regression tests for every fixed boundary.
