---
step_id: S267
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S267 — ProfileLabelAmbiguousError introduction

## Scope

Introduce `ProfileLabelAmbiguousError(WorkflowError)` in
`src/aeat/application/workflow/_errors.py` and replace the bare
`ValueError` raise at `_profile_bucket_scan.py:103` with the typed error.

## Outcome

### New error class

`ProfileLabelAmbiguousError(WorkflowError)` added to
`src/aeat/application/workflow/_errors.py`.

### Registry entry

`aeat.application.workflow._errors.ProfileLabelAmbiguousError` registered
in `src/aeat/core/errors/registry/_application.py` with:
- code: `REFUSED_PROFILE_LABEL_AMBIGUOUS`
- category: `REFUSED`
- message_key: `errors.refused.refused_profile_label_ambiguous`
- default_suggestion: `aeat config profile list`

### Raise site updated

`_profile_bucket_scan.py` imports `ProfileLabelAmbiguousError` and raises
it at the ambiguous multi-match path (formerly `ValueError`).

## Locale keys

`errors.refused.refused_profile_label_ambiguous` added to all locale files.

## Files touched

- `src/aeat/application/workflow/_errors.py`
- `src/aeat/application/workflow/_profile_bucket_scan.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/*.yml`

## Collision signal

`git diff -- <target files>` before edits: no output (clean).
