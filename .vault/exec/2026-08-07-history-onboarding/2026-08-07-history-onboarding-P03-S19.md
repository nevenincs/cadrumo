---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b81aae3827e8453bc0b5f3e7eb8ef262c56e4e0e4ba109a46614fc767d4d3d65'
step_id: 'S19'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add the expected-but-not-found advisory comparing captured rows against every PROFILE_APPLICABILITY-tagged pair, emitting a WARNING Notice naming each modelo and ejercicio the profile expects but no declaracion was captured for, verified by a test asserting the Notice fires only for PROFILE_APPLICABILITY pairs and never for pairs carrying only the AEAT_REGISTER_OPTIONS tag and ## Scope

- `src/cadrumo/application/live/_filed_data_capture.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the expected-but-not-found advisory comparing captured rows against every PROFILE_APPLICABILITY-tagged pair, emitting a WARNING Notice naming each modelo and ejercicio the profile expects but no declaracion was captured for, verified by a test asserting the Notice fires only for PROFILE_APPLICABILITY pairs and never for pairs carrying only the AEAT_REGISTER_OPTIONS tag

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `expected_but_not_found_notice`, warning only for profile-nominated pairs that produced no rows.

## Outcome

Fires ONLY for pairs carrying the profile signal. A pair nominated only by the
register's option list is never named however empty it came back, because that
list's informativeness for this taxpayer is unconfirmed — an alert derived from it
could be pure noise, and an advisory only earns trust if every firing is a real
finding.

A REFUSED pair is also never named, and that is the second half of the asymmetry.
The pair did not report "no filings"; it failed to report at all. Naming it would
tell the operator a filing is missing when nothing established that, while its
real failure row travels separately.

A pair carrying BOTH signals still warns: being also offered by the register must
not downgrade a profile expectation.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_onboarding.py -q -n0
    19 passed in 5.01s

Assertions read the notice CODE and machine-queryable CONTEXT rather than the
rendered message. The first version matched English prose and failed under a
Spanish ambient locale — the message is localised, so asserting on it would have
made the gate depend on the locale rather than on the behaviour.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
