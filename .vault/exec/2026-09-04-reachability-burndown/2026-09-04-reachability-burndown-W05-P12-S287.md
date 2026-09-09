---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e83db38ababe3f18773499b6b8feff258be3ad1921617ef0812cc35a718f824f'
step_id: 'S287'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only visible and exact workflow-resume convenience resolvers, migrate retained coverage to the live unified resume owner, run focused gates, classify the shared envelope-schema red, update cadence, and remeasure exact reachability.

## Scope

- `workflow resume production surface and focused resume tests`

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

- `M` `src/cadrumo/application/workflow/resume.py`
- `M` `src/cadrumo/application/workflow/tests/test_resume.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for visible/exact convenience resolvers -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused resume tests -> `6 passed, 7 peer-owned envelope-schema failures`
- `verify:` exact reachability -> `251 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

All seven focused failures terminate in the existing workflow envelope-header validation defect: `written_at`, `payload`, and `encryption` are rejected as extra fields while loading rows saved by the same suite. Both deleted wrappers and the live unified resolver reached that identical persistence path; the migration introduced no distinct failure.
