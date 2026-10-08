---
tags:
  - '#plan'
  - '#tui-profile-setup-ux'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-19-profile-setup-completion-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:170ba48a37b9bf8def4fbb6dbf82bcb66810a0bed56d836b225c4fad673eb594'
---

# `tui-profile-setup-ux` plan

## Description

Approved 2026-10-02. The operator requested a complete TUI profile creation and editing experience with clear steps, required and optional values, progress, collapsible detail, help, and affirmative completion; refresh the served PNG sets throughout the work.

Reuse the accepted interface decision D6 for the five-stage presentation and the accepted completion decision for the explicit guarded finish. This work changes presentation and development capture coverage, not persistence schemas, requirement policy, credential custody, or filing readiness. Existing broad interface-plan work remains outside this scoped revision.

## Steps

- [x] `S01` - Present navigable profile setup with skippable acquisition, required answers, review and truthful success; `src/cadrumo/entrypoints/tui/profile/overview.py, src/cadrumo/entrypoints/tui/profile/setup_journey.py, src/cadrumo/entrypoints/tui/secret/registration.py, src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py, src/cadrumo/entrypoints/tui/tests/test_manager_required_field_refusal.py, src/cadrumo/entrypoints/tui/tests/test_manager_masked_required_field.py, src/cadrumo/locales/*/flows.yml`.
- [x] `S02` - Capture profile creation, setup, editing and completion states in the served review gallery; correct layout defects exposed by those captures; `dev/tui/harness/surfaces.py, dev/tui/harness/profile_fixtures.py, dev/tui/harness/tests/test_profile_fixtures.py, src/cadrumo/entrypoints/tui/profile/overview.py, src/cadrumo/entrypoints/tui/secret/registration.py, src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py, src/cadrumo/locales/*/flows.yml`.

## Parallelization

One writer owns the profile screen, focused tests, translations and development capture registry. Preserve unrelated worktree edits. Another renderer currently owns the current gallery, so produce the profile review in an isolated named run until it can be safely refreshed.

## Verification

Exercise real profile registration, saves, required-only completion, optional skipping, backward navigation, refusal recovery, and saved completion with Textual pilots. Check 80x24, 120x40, 200x50 and 80x50 layouts in both appearances, and small layouts in all supported locales in generated captures. Run focused and owning TUI tests, Ruff format/lint, type checks and locale checks. Review the integrated change and rendered PNGs before reporting completion.
