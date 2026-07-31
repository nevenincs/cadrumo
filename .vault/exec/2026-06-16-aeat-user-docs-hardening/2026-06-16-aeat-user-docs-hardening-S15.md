---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:dd859fd6f8387f3d70725740e20ca5d1dedc769f86fb5b221c4ebe1669ebaa35'
step_id: 'S15'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden index.md

## Scope

- `docs/how-to/index.md`

## Description

- Verify-close: read `index.md` (the how-to landing/router page) against the hardening standard and confirm resolution at HEAD.
- Confirm the page is a question-first task router ("Pick the question closest to what you are trying to do") that links each how-to guide with imperative task labels; no first-person-plural, gerund-header, or self-praise anti-patterns.
- Confirm every linked how-to target resolves (relative markdown links) and the taxonomy matches the guides in the tree.

## Outcome

- Page verified compliant at HEAD. Delta: none required. CLI conformance gate green (the router carries no commands of its own).

## Notes

- Router-only page; its correctness is link integrity + task-label clarity, both sound.
