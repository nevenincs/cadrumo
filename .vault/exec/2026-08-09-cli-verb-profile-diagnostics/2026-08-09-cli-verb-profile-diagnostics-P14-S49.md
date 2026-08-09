---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:31a74bfc7b943a8054dc603673efa0985ca674766b57a48591c68431bae16264'
step_id: 'S49'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Replace the issue reference and phase language in the deferred-baseline finding message with a statement of the underlying technical fact, in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Rewrote the deferred-baseline finding's next-action string in all four catalogues, removing an issue number and the phrase describing the gap as deferred to a future phase, and stating instead that the bundled corpus publishes no baseline rate for that income type.
- Applied the same correction to the finding's source-side message text, which carried the same phase language.

## Outcome

An operator meeting this finding now reads why the value is unavailable, in terms that stay true regardless of how the work is scheduled.

Two things were wrong with the previous text, and only one of them is cosmetic. The issue number and phase language are project-management metadata, which this project forbids in user-facing surfaces because it means nothing to the person reading it. The deeper problem is that the sentence described a PLAN rather than a FACT: it would silently become false the moment the work was rescheduled, renumbered or completed, and nothing would fail. The replacement states the condition that actually holds, which stops being true only when the corpus itself changes - which is exactly when the message should change.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_finding_next_action_field_grounding.py -m "unit or integration" -n 0 -q
    4 passed in 1.02s

A catalogue-wide sweep for the issue-reference and phase-language patterns now returns nothing in any of the four files.

## Notes

Found while verifying an adjacent Step owned by a concurrent author. That Step's own subject - grounding this message's FIELD NAME - was already implemented correctly by its author and was deliberately not touched or closed here. Only the process-metadata defect, which that Step does not cover, was addressed.
