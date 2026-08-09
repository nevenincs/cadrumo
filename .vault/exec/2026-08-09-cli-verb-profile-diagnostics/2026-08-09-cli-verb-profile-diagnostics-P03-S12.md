---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d49ffc801e9a5fe6e5aaf118cda4dcb58d0ccd683d9b340e127f0cd252f732f2'
step_id: 'S12'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Replace the diagnostics profile-readiness bare-count summary with one naming the missing fields by operator label

## Scope

- `src/cadrumo/application/diagnostics.py`

## Description

- Replaced the count-only summary with `cli.diagnostics.summary.profile_missing_fields`, which carries both the count and the rendered field list.
- Built the list from the same findings tuple the check already returns, so the summary and the detail cannot disagree about which fields are missing or how many.
- Removed the superseded count-only locale key from all four catalogues after confirming no remaining reference.

## Outcome

The readiness summary names the fields rather than counting them.

Building the list from the findings tuple rather than recomputing it is the substantive part. The previous code summed two lengths independently of the tuple it returned, so a change to either branch could have produced a summary whose count disagreed with the rows beneath it. There is now one source for both.

This changes only the diagnostic's TEXT. Which fields are considered missing is decided upstream, and that decision is untouched.

## Verification

    uv run --no-sync pytest src/cadrumo/application/tests/test_diagnostics_profile_grounding.py -n 0 -q
    4 passed in 2.36s

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

## Notes

This check is one of the three surfaces whose READINESS VERDICT was deliberately deferred. That deferral is untouched: the verdict is computed upstream and only its rendering changed here.
