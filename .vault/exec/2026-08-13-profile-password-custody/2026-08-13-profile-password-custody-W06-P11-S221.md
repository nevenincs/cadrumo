---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d62bc966b8e2b752c90b201f6a396c23eaabe8714a727f385268646bb62136ee'
step_id: 'S221'
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
     The S221 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Re-run the complete S206 recovery-enrollment matrix across interactive, TUI, stdin, POSIX descriptor, Windows inherited-handle, mismatch, cancellation, collision, and publication-failure paths and persist the resulting evidence and ## Scope

- `src/cadrumo/application/user_profile/tests/test_recovery_enrollment_at_creation.py and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/adapters/inbound/tui/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-run the complete S206 recovery-enrollment matrix across interactive, TUI, stdin, POSIX descriptor, Windows inherited-handle, mismatch, cancellation, collision, and publication-failure paths and persist the resulting evidence

## Scope

- `src/cadrumo/application/user_profile/tests/test_recovery_enrollment_at_creation.py and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/adapters/inbound/tui/tests/`

## Description

- Re-run the mandatory recovery-at-creation application, storage, scripted CLI, terminal, TUI, subprocess-platform, and harness lanes against current HEAD.
- Repair the shared scripted profile-create helper to perform the real paired recovery handoff and exact possession proof.
- Wait for the TUI recovery widgets to mount before driving exact masked re-entry, eliminating a presentation race without bypassing verification.
- Run scoped Ruff and ty gates and submit the changes and matrix evidence for independent review.

## Outcome

The recovery matrix passed 58 tests with one expected platform skip on this Windows host:

| Lane | Result |
| --- | --- |
| Application enrollment, password-login independence, recovery codec, scripted CLI refusal/success matrix | 45 passed |
| Terminal wizard and full-screen TUI exact proof/cancel/mismatch/shutdown paths | 8 passed |
| Scripted stdin/fd leaf channels plus Windows inherited-HANDLE and POSIX `pass_fds` transports | 3 passed, 1 POSIX skip |
| Harness provisioning and active-profile delivery | 2 passed |

Exact commands:

- `pytest -m integration -q` over `test_recovery_enrollment_at_creation.py`, `test_password_login_recovery_independence.py`, `test_recovery_secret_codec.py`, and `test_scripted_profile_creation.py`: 45 passed.
- `pytest -m integration -q` over `test_registration_recovery_words.py` and `test_profile_create_wizard.py`: 8 passed.
- `pytest -m integration -q` selecting `test_profile_create_succeeds_through_each_leaf_channel`, `test_windows_recovery_handles_complete_real_headless_creation`, and `test_posix_recovery_descriptors_complete_real_headless_creation`: 3 passed, 1 skipped.
- `pytest -m integration -q` selecting the two harness active-profile delivery tests: 2 passed.
- Scoped `ruff check` and `ty check` on both modified test-support files: clean.

## Notes

The POSIX transport test is correctly platform-skipped on Windows; its Windows counterpart ran through real inherited handles and a real subprocess. A broader taxpayer-type module has three unrelated stale expectations: legal-form creation now deliberately publishes an incomplete profile, IRNR creation now directs setup completion rather than M210, and a legal-to-natural edit no longer refuses missing surnames. The first two initially exposed the missing recovery pipes in the shared helper; after that regression was repaired, all three resolve beyond the recovery boundary and remain owned by taxpayer-completeness/next-action semantics.
