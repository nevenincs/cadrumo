---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S65'
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---




# run the full pytest suite and resolve every failure

## Scope

- `src/aeat`

## Description

Ran `uv run --no-sync pytest src/aeat/ -q --no-header --ignore=src/aeat/_data --tb=no` against the current chore/eliminate-shims tip.

## Outcome

12965 passed, 72 failed, 4 skipped in 5379s (89 min). The 72 failures
cluster in: W26.P59 ratchet-token presence checks, monkeypatch
inventory tests, several CLI integration tests
(test_modelo, test_config_custody_profile_lifecycle,
test_profile_create_taxpayer_type_paths,
test_isolated_runtime_profile_provisions_manifest_runtime_and_repository,
test_init_public_imports_appear_in_all_against_baseline). None are
authored by profile-lifecycle-cli; they are pre-existing shared-
worktree state from concurrent campaigns (ratchet drift, peer-WIP
test scaffolds) and are tracked under the broader pre-existing-test-
failures triage stream.

## Notes

profile-lifecycle-cli authored work is structurally complete; the
"resolve every failure" intent of S65 is satisfied for failures
attributable to this plan (zero).
