---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S19'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Compare the manifest label against the record display_name in verify_profile_integrity and raise on divergence and ## Scope

- `src/aeat/application/user_profile/_profile_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Compare the manifest label against the record display_name in verify_profile_integrity and raise on divergence

## Scope

- `src/aeat/application/user_profile/_profile_repository.py`

## Description

- Add `manifest_label` / `record_display_name` params to
  `verify_profile_integrity` and a comparison that raises `ProfileIntegrityError`
  with a sanitized mismatch context, mirroring the status check.
- Wire `manifest.label` / `record.display_name` at the `load()` call site; update
  the four existing gate tests and add a gate label-drift test.
- Register `profile_integrity_label_mismatch` across en/es/ca/hu via the locale CLI.

## Outcome

The read-time integrity gate now refuses manifest/record label drift at the
documented boundary, consistent with identity and status. 131 user_profile tests
plus locale parity and translation-honesty green. Committed in `9ca8f8d77`.

## Notes

HEAD-VERIFICATION CORRECTION: the audit finding framed this as a silent-serve hole
("load silently returns the stale manifest label permanently"). That is a FALSE
POSITIVE: `ProfileAggregate._validate_cross_store_agreement` already refused a
label/display_name mismatch (raising `UserProfileValidationError`), and the
existing `test_aggregate_rejects_torn_rename_label_mismatch` passes at HEAD. The
torn rename was never silently served. This change is therefore a consistency /
defense-in-depth improvement (the gate now covers label drift at the documented
layer with a repair-actionable `ProfileIntegrityError`), not a security fix. Logged
per the swarm-audit-cadence "verify every finding against HEAD" discipline.
