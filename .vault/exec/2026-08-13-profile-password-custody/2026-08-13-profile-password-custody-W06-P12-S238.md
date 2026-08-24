---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0a6be57cf863c8b40c1b22315af1c14b96e1777a6af01d633c68ad0b84b2b163'
step_id: 'S238'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S238 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Remove inactive profile deletion from the root login gate while preserving active-profile refusal, explicit confirmation, custody preflight, and exact target binding in real subprocess execution and ## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py and src/cadrumo/entrypoints/cli/_config/_profile_delete.py and src/cadrumo/entrypoints/cli/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove inactive profile deletion from the root login gate while preserving active-profile refusal, explicit confirmation, custody preflight, and exact target binding in real subprocess execution

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py and src/cadrumo/entrypoints/cli/_config/_profile_delete.py and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/application/config_reset.py and src/cadrumo/application/user_profile/_custody_repository.py and src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/user_profile/_custody_transactions.py and src/cadrumo/application/user_profile/_lifecycle.py and src/cadrumo/application/user_profile/tests/test_custody_transactions.py`

## Description

- Reclassify exact profile deletion from the root login-gated registry to a
  dedicated sessionless target-destruction leaf exemption.
- Preserve exact label resolution, active-pointer refusal, confirmation,
  retention assessment, and journal-bound custody destruction at the leaf.
- Remove the in-capsule bucket lock from the Windows rename span while retaining
  custody transaction locking and immutable inventory revalidation.
- Persist inactive-only authority in the custody journal and revalidate it under
  the canonical reentrant pointer transaction before destructive owner effects.
- Add real subprocess proofs for logged-out inactive deletion success and active
  deletion refusal, including post-state listing assertions.

## Outcome

Logged-out operators can delete only an exact inactive named profile through the
real root entrypoint. Active deletion still returns the typed boundary refusal
and leaves the profile active and listed. The admission record cites both
subprocess proofs so later drift makes the exemption gate fail.

## Notes

- RAG discovery grounded the change in the accepted per-profile custody ADR and
  located the stale negative admission beside the sessionless deletion owner.
- Exact subprocess tests passed 2 tests; admission, login-gated, profile-delete,
  and destructive-confirmation suites passed 89 tests; command graph and
  authentication posture passed 38 tests; Ruff and ty passed.
- The durable crash/resume guard passed natively and under WSL/POSIX; final
  formal review passed with no remaining findings.
- The complete subprocess lifecycle module passed 17 tests and failed 3
  unrelated host/stale-expectation cases: two require unavailable OS-keychain
  persistence and one expects retired wording.
