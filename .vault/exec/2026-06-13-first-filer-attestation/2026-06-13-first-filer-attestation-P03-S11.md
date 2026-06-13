---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S11'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Fail closed with a blocking finding that prompts the operator to record the activity-start date when the profile carries no activity_start_date at all, so the gate never silently opens

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Emit `_cross_period_missing_activity_start_finding`: a BLOCKING finding prompting the operator to record the activity-start date when an evidence-missing dependency blocks AND the profile carries no `activity_start_date` at all.
- Gate the fail-closed finding on a curated `_FIRST_FILER_CANDIDATE_BLOCKERS` set so non-first-filer flows with clean cross-period verdicts are unaffected.

## Outcome

- Landed in commit `5d6549183`. The gate fails closed instructively rather than silently opening. Proven by P04.S16 `test_verify_fails_closed_when_profile_records_no_activity_start_date`.

## Notes

- Fires only when an evidence-missing dependency a genuine first filer would hit blocks; a clean verdict never triggers it, so existing flows do not regress.
