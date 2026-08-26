---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:0916c2a8d0a25e2cc911106d26a99bd9ebff96be838c3f9c08b35d8c504f6e73'
step_id: 'S21'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove exact operation binding expiry single use mismatch refusal cancellation cleanup and canary non-retention through real secret journeys

## Scope

- `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/secret/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `M` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py -q -m integration` -> `pass` (9 passed)

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

## Notes

Scoped to PassphraseApp (the new build) plus the CredentialApp base it shares with Login/Registration: single-use dispatch, exact refusal binding, cancellation, and canary non-retention. Login and Registration already carry their own real-journey coverage (test_login_screen.py, test_registration_screen.py, test_registration_recovery_words.py, test_registration_language_switch.py); this file does not duplicate that.

Added a parametrized real-geometry proof (narrow/medium/wide) asserting every field and button has a positive, in-viewport region -- direct follow-up to the SourceActionCard height defect found during the S17-S19 relocation, per operator direction that presence and focus assertions alone had already been shown insufficient.
