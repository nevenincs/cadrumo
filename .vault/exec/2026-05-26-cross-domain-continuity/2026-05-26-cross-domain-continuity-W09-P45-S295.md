---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S295'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# W09 wording follow-up Tier-2 import-collision tr() default text reads 'already taken by a different profile' regardless of fresh_uuid_mode

## Scope

- `misleading in the fresh-copy path`
- `distinguish UUID-collision vs label-collision messages`
- `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

- Ground the step with RAG against the profile-import collision plan row and current code path.
- Keep the current D5 import behavior unchanged: bundle UUID collisions are refused before label handling, and `--label` remains label-collision recovery, not fresh-UUID creation.
- Reword `cli.config.profile.import_label_taken_different_id` in the English, Spanish, Catalan, and Hungarian locale files so Tier-2 output says the profile label is already in use instead of implying a different profile identifier.
- Reword `cli.config.profile.import_label_help` in the same locale files so `--label` is described as stored-label collision recovery, not as fresh-copy creation.
- Add real CLI integration assertions to `test_profile_import_idempotency` proving UUID-collision output and label-collision output are distinct, including the explicit `--label` refusal path.
- Resolve reviewer drift by updating the test contract prose from old "already registered" wording to the current UUID-collision wording.

## Outcome

S295 is closed as an operator-message hardening and regression pin. The implementation already had separate UUID-collision and label-collision translation keys; this step removed stale "different identifier" wording from the Tier-2 label-collision message, removed stale fresh-copy wording from the `--label` help text, and pinned the distinction through the real CLI.

The review found one low issue: stale test prose still described UUID collisions as "already registered" while the executable assertion now checks for UUID/conflict wording. That was corrected before closure.

## Notes

Validation:

- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py -q -p no:cacheprovider` passed with 11 tests.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py` passed.
- `uv run --no-sync python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `git diff --check` passed for the S295 path set, with only existing CRLF normalization warnings on locale files.

No production import behavior changed. No raw profile UUIDs are asserted or leaked in public-output expectations.
