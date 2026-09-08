---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:ed7c53e66c2c84fb1fe773b28be29338ad623de5b69e9a7f87c4578d39e5c6e4'
step_id: 'S228'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the zero-consumer unapprove_draft writer and the two documentation claims that publish it as a supported review transition; preserve approval invalidation and the accepted immutable-revision recovery rule, where recovery creates an explicit successor rather than clearing approval metadata in place.

## Scope

- `Filing draft review implementation and package documentation`
- `accepted evidence revision identity decision`
- `exact symbol signal`
- `focused approval and supersession gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

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

- `M` `src/cadrumo/application/filing/draft_review.py`
- `M` `src/cadrumo/application/filing/__init__.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/draft_review.py src/cadrumo/application/filing/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s228 src/cadrumo/application/filing/tests/test_filing.py src/cadrumo/application/filing/tests/test_review_runtime_storage.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit exits 1 on the remaining backlog, as designed. This step reduced reachable-module unused-symbol findings from 306 to 305 while leaving 51 unreachable modules and four orphaned test modules unchanged. Exact code/dev search found no surviving `unapprove_draft` reference before or after deletion; the package facade is inert and had only advertised the unsupported transition in prose.
