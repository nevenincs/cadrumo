---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S283'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# HARDCODED_USER_STRING sweep S98 follow-up: route 9 BadParameter raises in diagnostics/profile.py via tr() (lines 62 66 68 72 77 98 104 117 127-128 153)

## Scope

- `bulk locale-CLI migration`
- `coin keys under diagnostics.profile.errors namespace`
- `src/aeat/diagnostics/profile.py`

## Description

- Ground S283 with RAG against the open cross-domain plan row and current diagnostics/profile localization references.
- Verify that `src/aeat/diagnostics/profile.py` is absent in the current worktree.
- Trace the removed path with `git log --follow` and confirm it was deleted by the unapproved diagnostics package removal.
- Inspect the last pre-delete file version and confirm the targeted refusal helpers already routed through `tr("cli.diagnostics.profile.errors.*")`.
- Search current approved diagnostics/profile-adjacent sources for live `BadParameter` residuals and retired `aeat.diagnostics` registrations.
- Treat S283 as a no-code closure because the targeted production surface no longer exists and no approved replacement carries the defect.
- Run a scoped review of the no-code closure evidence.

## Outcome

S283 is closed with no production-code change. The plan row targeted a retired source package, `aeat.diagnostics`, that was removed as an unapproved production package in `d695b5ff7`. The last pre-delete `profile.py` implementation already localized the listed refusal helpers under `cli.diagnostics.profile.errors.*`, and current approved diagnostics/profile-adjacent modules do not contain the targeted `BadParameter` sites.

## Notes

Validation:

- `uvx vaultspec-rag search "W09 P45 S283 diagnostics profile BadParameter locale tr hardcoded user string" --type vault --doc-type plan` returned the open S283 row targeting `src/aeat/diagnostics/profile.py`.
- `uvx vaultspec-rag search "diagnostics profile BadParameter validation errors profile diagnostics CLI locale tr" --type code` returned current localized `BadParameter` patterns, not a live diagnostics-profile implementation.
- `Test-Path src/aeat/diagnostics/profile.py` confirmed the target file is absent.
- `git log --oneline --follow -- src/aeat/diagnostics/profile.py` identified `d695b5ff7 chore: remove unapproved diagnostics source package`.
- `git show d695b5ff7^:src/aeat/diagnostics/profile.py` confirmed the pre-delete refusal helpers used `tr("cli.diagnostics.profile.errors.*")`.
- `rg -n "BadParameter\(" src/aeat/entrypoints/cli/_config/_repair_profile.py src/aeat/entrypoints/cli/_config/_auth_diagnostics.py src/aeat/application/diagnostics.py` returned no matches.
- `rg -n "aeat\.diagnostics|diagnostics\.profile|cli\.diagnostics\.profile|python -m aeat\.diagnostics" src/aeat pyproject.toml .vault/plan/2026-05-26-cross-domain-continuity-plan.md` found only the stale plan row in live source/project scope.
- `uv run --no-sync pytest src/aeat/application/tests/test_config_parity.py::test_retired_config_profile_set_is_not_registered -q` passed.
- `uv run --no-sync pytest src/aeat/application/setup/tests/test_cli.py::test_setup_profile_help_exposes_review_and_validation -q` passed.
- `git diff -- src/aeat/diagnostics/profile.py src/aeat/application/diagnostics.py src/aeat/entrypoints/cli/_config/_repair_profile.py src/aeat/entrypoints/cli/_config/_auth_diagnostics.py src/aeat/locales` produced no diff.

Notes:

- Executor Wegener independently recommended `NO-CODE-CLOSURE` and changed no files.
- The source locale files also no longer contain `cli.diagnostics.profile.errors.*` leaves because no live source references the retired namespace.
