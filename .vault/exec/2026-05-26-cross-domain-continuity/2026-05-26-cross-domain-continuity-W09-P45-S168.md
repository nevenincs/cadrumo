---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S168'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# extract _covered_by_namespace to one location and import from the other

## Scope

- `src/aeat/locales/`

## Description

`_covered_by_namespace` was duplicated in both
`src/aeat/locales/cli.py` (line 112) and
`src/aeat/locales/manager.py` (line 426) with identical bodies.
Deleted the cli.py copy; added it to the cli.py import line from
manager.

## Outcome

Real refactor. 27 locale tests
(test_cli.py 9 + test_locale_translation_honesty.py 2 +
test_parity.py 16) pass after the dedup.

## Notes

manager.py copy was kept as the canonical because it carries the
docstring; cli.py copy was a bare-body duplicate.
