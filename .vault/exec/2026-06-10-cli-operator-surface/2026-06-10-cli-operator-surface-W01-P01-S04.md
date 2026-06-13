---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S04'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# narrow the work verify --select choices to the states verify accepts so latest-verified and filed stop being advertised-but-impossible, satisfying the new gate

## Scope

- `src/aeat/application/modelo/_selectors.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`
- `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

The verify `--select` option was a bare `str` whose help/error text advertised
all five `ModeloCalculationRevisionSelector` members, while `verify` refuses any
revision not in `BORRADOR` (only `current`, `latest-draft`, `explicit` can reach
a draft). Added a dedicated `ModeloVerifySelector` StrEnum (the three
draft-reachable members) in `_selectors.py`, re-exported it at the package top
level, and typed the verify `--select` option as it so click advertises a
3-member `Choice`. `to_calculation_revision_selector()` maps each verify member
to its full-selector member for the existing resolver. The `file` command and
`work revision --select` keep the full five-member enum, undisturbed.

Added a `cli.app.modelo.work.verify_selector_help` key (distinct from the shared
`revision_selector_help`) across all four locales.

## Outcome

`work verify --select` advertises exactly `current` / `latest-draft` /
`explicit`; `latest-verified` and `filed` are no longer advertised-but-impossible.
The D5 enum-choice surface passes, the modelo work UX integration test passes,
and the selectors unit tests pass. `aeat.locales scaffold --check` clean. No docs
cited `verify --select latest-verified` (the only documented verify selector is
`latest-draft`, still valid).

## Notes

`ModeloVerifySelector` member values equal the matching
`ModeloCalculationRevisionSelector` values, so the mapping is total. Other
commands sharing the full selector enum were intentionally left unchanged.

