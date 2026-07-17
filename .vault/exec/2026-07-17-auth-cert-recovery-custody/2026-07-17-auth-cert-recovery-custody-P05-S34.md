---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S34'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S34 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Require yes for auth reset while keeping auth status and auth test non-destructive and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Require yes for auth reset while keeping auth status and auth test non-destructive

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`

## Description

Closed the S34 destructive-guard contract in `test_destructive_verbs_require_yes.py`: `config auth reset` requires an explicit `--yes`, while `config auth status` and `config auth test` stay non-destructive and need no confirmation.

- Confirmed the `auth reset` door refuses before any backend mutation when `--yes` is omitted, and that `test_auth_reset_refuses_without_yes` proves it (the door raises the localised `reset_requires_yes` refusal at the CLI boundary).
- Added `test_auth_status_is_non_destructive_and_needs_no_yes`: the recorded-state read verb runs against an unconfigured profile, exits 0, and its output carries no `--yes`/confirm guard.
- Added `test_auth_test_is_non_destructive_and_needs_no_yes`: the live-probe verb runs with a configured certificate provider, never mutates provider state, and demands no confirmation. Both are anti-tautology companions proving the `--yes` guard is scoped to `reset` alone.

## Outcome

Step complete. The four auth guard tests pass (`test_auth_reset_refuses_without_yes`, `test_auth_logout_does_not_require_yes`, and the two new non-destructive companions): 4 passed, ruff clean, collect-only clean. Source change committed as `c3c7532282`.

## Notes

The `auth reset` door already required `--yes` (landed with the P01 auth logout/reset separation); this step adds the previously-missing explicit proof that `auth status`/`auth test` stay non-destructive, completing the step's full subject. Real-CLI runner throughout; no mocks/skips.
