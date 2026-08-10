---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d1d051abc5a5ff4bbaed9dfe58f8cb3284dd7ec0fc8fc532951ab1611a61cd9b'
step_id: 'S04'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-08-09-cli-action-envelope-hardening-plan placeholders are machine-filled by
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
     The Require every census candidate to carry exactly one current disposition and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
