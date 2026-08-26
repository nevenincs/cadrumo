---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fe16d4c785b1a90ff5104a2bd998dbc7dea6a9be89ad32c47b94980022c829c6'
step_id: 'S05'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Publish the settled profile presentation contract through the application facade

## Scope

- `src/cadrumo/application/user_profile/presentation.py public defining module`

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

- `M` `src/cadrumo/application/user_profile/presentation.py`

## Notes

No `__init__.py` change: `aeat-architecture-boundaries` makes every package
`__init__.py` inert (no re-exports, aliases, or facades), so "publish
through the application facade" is satisfied by `presentation.py` itself
being the canonical PUBLIC defining module (not `_presentation.py`), with
its complete public contract stated in its own `__all__`
(`ProfileFieldClassification`, `ProfileFieldPresentationV1`,
`ProfileFieldSourceClass`, `ProfilePresentationV1`,
`build_profile_presentation`, `profile_field_source_class`). A consumer
imports directly from `application.user_profile.presentation`. This is the
same judgement already applied and accepted for W05.P11.S65.