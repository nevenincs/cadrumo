---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d47aee2eaf762f69a02978ac63082ae252c09a68f27fae4925098d9101023e80'
step_id: 'S13'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Replace the raw profile keys carried in diagnostics findings with schema-derived labels and legal basis

## Scope

- `src/cadrumo/application/diagnostics.py`

## Description

- Added `_grounded_profile_key_summary`, rendering a bare profile path as `path - label` through the canonical requirement builder, and returning the key unchanged when the schema does not resolve it.
- Applied it to both branches that previously emitted a bare key: the wizard-report fallback for missing required keys, and the missing-enrolment keys.

## Outcome

A field reaching the diagnostics row through the fallback branch is now named the same way as one reaching it through the record probe, which already emitted the labelled form.

The path is kept AHEAD of the label rather than replaced by it, for two concrete reasons. The enrolment de-duplication immediately above splits each summary on the separator to compare paths, so putting the label first would have silently broken that comparison and reported already-named enrolment keys a second time. And the path is what an operator types at the profile editor, so it is useful rather than noise.

An unresolvable key is returned unchanged rather than given an invented label.

## Verification

    uv run --no-sync pytest src/cadrumo/application/tests/test_diagnostics_profile_grounding.py -n 0 -q
    4 passed in 2.36s

The de-duplication constraint is covered directly by `test_the_rendered_form_keeps_the_path_first_so_deduplication_still_works`, which asserts the segment before the separator is still exactly the path.

## Notes

The two branches previously disagreed on formatting, which is why the same field could appear two different ways in one operator's output depending on whether the record probe was readable.
