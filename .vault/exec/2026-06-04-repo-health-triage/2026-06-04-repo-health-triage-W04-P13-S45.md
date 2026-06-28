---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P13.S45'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P13.S45 - Resolve submission draft-path Vulture candidate

Scope: Close the Vulture candidate for
`src/aeat/domain/submission/_protocols.py` without changing submission engine
behavior.

## Description

- Make `ModeloDraftLoader.load()` define its draft path argument as
  positional-only and underscore-prefixed.
- Preserve the `Path` input and `ModeloDraftLike` return contract.
- Verify that Vulture no longer reports the submission protocol parameter while
  leaving the final W04.P13 CLI documentation candidates open.

## Outcome

The submission draft loader protocol no longer exposes a named unused parameter
that Vulture treats as dead code. The protocol still requires loaders to accept
one draft path argument and return a `ModeloDraftLike`.

## Notes

No call sites were found that use `ModeloDraftLoader.load(draft_path=...)` as a
keyword call. A broader adapter repository compatibility test run exposed an
unrelated `ClassificationError` empty-message assertion failure; the scoped
domain submission suite passed. Remaining Vulture findings belong to
W04.P13.S46.
