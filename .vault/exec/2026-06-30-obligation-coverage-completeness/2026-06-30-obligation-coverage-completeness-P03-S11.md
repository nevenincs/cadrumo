---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:4e73317f541b3fe68b75ed3cf57316bccdc2972b62acdcb7768fe3329c404142'
step_id: 'S11'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Harden the out-of-scope hatch with a gate asserting it cannot silence an applicability-decidable modelo.

## Scope

- `src/aeat/application/overview/tests/test_obligation_coverage.py`

## Description

- Add a gate asserting every `OUT_OF_SCOPE_OBLIGATIONS` entry carries a non-empty
  recorded reason.
- Add a gate asserting no out-of-scope modelo has a seed applicability rule, so the
  hatch cannot silence an obligation the applicability table can positively decide.

## Outcome

Misuse of the out-of-scope escape hatch is now a hard test failure rather than a
silent under-scoping. Both gates pass for the current declaration (036/151/714/840).

## Notes
