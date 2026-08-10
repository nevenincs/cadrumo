---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:74177623d2469a85a18f4997be248c1cf4f8761db8ec46146fd8e96b40ca7fe8'
step_id: 'S04'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Require every census candidate to carry exactly one current disposition

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`

## Description

- Require the checked-in action-disposition ledger to reconcile bidirectionally with the AST census.
- Classify known workflow, wizard, authentication, modelo, profile-repair, and ledger command chains as producers.
- Require every non-action ledger exclusion to carry a distinct, source-specific semantic rationale.

## Outcome

Every current census candidate has one adjudicated disposition. The focused conformance gate rejects missing, stale, or semantically generic disposition coverage without relying on a fixed candidate count.

## Verification

```
python -m dev.cli_action_census_dispositions HEAD
reconciled 1265 CLI action-census dispositions against HEAD

uv run --no-sync pytest -n0 dev/tests/test_cli_action_census_dispositions.py -q
10 passed in 35.26s

uv run --no-sync pytest -n0 -m integration -q <three focused S04 node IDs>
3 passed in 60.05s

uv run --no-sync ruff format --check <S03 module, S03 tests, S04 test>
3 files already formatted

uv run --no-sync ruff check <S03 module, S03 tests, S04 test>
All checks passed!

uv run --no-sync basedpyright <S03 module, S03 tests, S04 test>
0 errors, 0 warnings, 0 notes

git diff --check -- <S03 module, S03 tests, S04 test>
exit 0
```

Independent review closed all findings for the W01.P01 evidence slice.

## Notes

The broad fifteen-test integration selection was deliberately not used as closure evidence. The three focused S04 tests exercise the disposition-coverage contract introduced by this Step.
