---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7dbb1caeac341b8ade7097e724e8a7343fa3a5c19122e4a71775eedd07731723'
step_id: 'S62'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Pin the bootstrap pre-emption itself so relocating tree materialisation out of bootstrap reds loudly rather than silently redistributing which surface answers a missing or occupied path, gated by a test naming the pre-emption as its subject

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Search for an existing pin naming the bootstrap tree-materialisation pre-emption as its subject before writing a new one.
- Find `test_bootstrap_refuses_an_occupied_directory_before_check_can_report_it` in the sibling test module, landed as part of the earlier CLI-surface pinning work; its own docstring already states the property this Step asks for ("Pins the pre-emption above as behaviour rather than a comment... a future change that moved tree materialisation out of bootstrap would silently make `check` the reporter instead").
- Run a real mutation proof rather than trusting the docstring: comment out the root callback's `_ensure_storage_tree_for_invocation()` call, confirm the pin reds, restore the exact original line, confirm `git diff --numstat` reports zero net change, and confirm the pin is green again.

## Outcome

No new test needed: the pin already exists, landed in `672c88cf4` ("test(cli): pin the config storage surface through the real command tree", the Step immediately before this one in the plan), and the mutation proof confirms it is load-bearing rather than a stale docstring claim.

Mutation: commented out the single line `_ensure_storage_tree_for_invocation()` in the CLI root callback. Result: `test_bootstrap_refuses_an_occupied_directory_before_check_can_report_it` failed with `AssertionError: assert 'warning' == 'error'` — exactly the redistribution the Step warns about: with the pre-emption gone, `config storage check`'s own body reports the occupied-directory drift as a non-fatal warning instead of the bootstrap refusing the whole invocation as an error. Restoration: `git diff --numstat` on the file reported no output (zero lines changed, byte-identical to HEAD); the test passed again immediately after.

The Step's cited file location (`src/cadrumo/entrypoints/cli/_config/tests/`) is the plan's stale citation — the pin actually lives in the sibling `src/cadrumo/entrypoints/cli/tests/test_config_storage_surface.py`, alongside every other `config storage` CLI-surface test, not in the `_config` package's own test folder.

## Notes

No source or test file changed; this Step closes on verification of already-landed work plus the mutation proof.
