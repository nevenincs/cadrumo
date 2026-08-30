---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4705230ec8400fbb22f95d39edaa6d9a1af2e376146dc50dd1cc292cbeccf829'
step_id: 'S334'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Repair the attestation authority's git invocation, which cannot read any blob: the dependency-receipt attestation path shells out to a `git view <sha>:<path>` subcommand that does not exist in git, so every blob read fails and five receipt tests fail on it. OBSOLETE AS OF 2026-08-28 -- DISCHARGED BY DELETION, NOT BY REPAIR, and left unchecked deliberately so the two dispositions do not wear the same checkbox. The defect was real and was located exactly: `_run_git_bytes(workspace_root, "view", f"{commit}:{relative}")` at line 484 of `src/cadrumo/entrypoints/tests/test_public_operation_dependency_receipt.py`. Commit 00de767e9a, which retired the C0 dependency receipt apparatus, DELETED that file outright. The row's own copy-check instruction was carried out and is clean: every surviving git subprocess in the tree uses a real subcommand, the only correct blob read is `git show` in `dev/audit/write_site_census.py:365`, and the remaining `"view"` tokens are the operator-surface CRUD verb and a docs config value, neither of them a git argument. So there is nothing left to repair. DECISION REQUIRED: close this row as discharged-by-deletion with this record as its evidence, or reopen it against a successor if the attestation path is ever rebuilt. Do NOT simply check it -- the subject was removed rather than fixed, and the campaign's own rule is that delivered-as-specified and recorded-but-not-implemented must not be indistinguishable

## Scope

- `the attestation authority's git subprocess invocation and the receipt tests that exercise it`

## Changes

- `verify:` `rg -n '"view"' src/ dev/` -> `pass`

## Notes

No code change. The subject was removed, not repaired: commit `00de767e9a`
("refactor(operations): retire the C0 dependency receipt apparatus") deleted
`src/cadrumo/entrypoints/tests/test_public_operation_dependency_receipt.py`,
which carried the `git view` invocation at its line 484. Verified at
`c9e5cd7cc4`: that file is absent from `src/cadrumo/entrypoints/tests/`, and
the row's copy-check is clean -- every surviving `"view"` token in the tree is
the operator-surface CRUD verb (`application/operator_surface/crud_contract.py:33`),
a devtools subparser (`entrypoints/tui/devtools/__main__.py:92`), or a CLI
argument. None is a git subcommand.

Recorded as discharged-by-deletion so this disposition stays distinguishable
from delivered-as-specified. Reopen against a successor if the attestation
path is ever rebuilt.
