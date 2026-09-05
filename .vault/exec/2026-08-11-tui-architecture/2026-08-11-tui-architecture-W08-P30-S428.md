---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:8bfdbb897c1662c2f51fd81813109636d653b35e657e50ea7f45d13d291120c6'
step_id: 'S428'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Make the test suite's output-language pin actually pin the language. The flow-TUI locale gates fail on their FIRST assertion, before any switch: under output_language_scope(EN) the screen renders Spanish. The pump boundary is not the cause. load_settings() returns a context-local override in preference to the environment, and cadrumo/conftest.py opens a session-scoped override_settings block, so the helper's CADRUMO_OUTPUT_LANGUAGE write was inert for the entire suite and every pinned language silently resolved to the configured default. Carry the language into the active override in place -- in place because the object is reached through a ContextVar and a replacement would need a Token that cannot be reset from a message-pump callback's asyncio Context.

## Scope

- `src/cadrumo/tests/env_scope.py`
- `src/cadrumo/core/i18n/tests/test_output_language_scope.py`

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

The two flow-TUI locale gates were reported as a message-pump problem. They
are not. Both fail on their FIRST assertion, before any switch happens: under
`output_language_scope(EN)` the screen already renders `es-copy`. Nothing had
crossed a pump boundary yet.

`load_settings()` returns a context-local override IN PREFERENCE to the
environment, and `cadrumo/conftest.py` opens a session-scoped
`override_settings` block. So the helper's `CADRUMO_OUTPUT_LANGUAGE` write was
inert for the entire suite. Measured directly: env `'en'`, override's
`cadrumo_output_language` `ES` with `model_fields_set` False, resolved `es`.
Every test that pinned a non-default language was really asserting about
Spanish, and reported nothing.

The fix carries the language into the active override IN PLACE. In place is the
whole point: the override is reached through a ContextVar, so a replacement
would need `ContextVar.set`, whose Token cannot be reset from a different
asyncio Context -- which is exactly where a Textual message-pump callback runs.
Every context already holds a reference to the same object, so an in-place
write crosses that boundary needing no Token at all. That is the part the
original pump diagnosis got right, applied to the wrong layer.

`model_fields_set` is maintained alongside the value because the resolver
distinguishes an explicit choice from a default that flowed through. Unsetting
removes the field rather than writing a default into it; otherwise "unset" and
"chose the default" stop being distinguishable for every later test in the
session.

Three gates, in their own module because the failure is invisible from the call
site -- the helper reports nothing, the block runs, only the resolved language
is wrong. The pin beats an override that named a DIFFERENT language explicitly
(the sharpest form: it must beat a deliberate choice, not a default); the
mid-block switch reaches the override too, which is the half message-pump
callers depend on; and both restore directions are checked, because an override
that never mentioned a language must not come back carrying one.

Teeth: `settings_override.get()` replaced by `None`. All five gates failed --
the three new ones and both flow-TUI gates. Restored by copy; defect count 0.

## Notes

The sibling writer committed this file in `dc99c8a896` while the injected
defect was still in it, so HEAD carries
`override = None  # defect: pin never reaches the override`. The working tree
holds the correct line and is uncommitted. This needs a commit to land.

Three failures in `src/cadrumo/core/i18n/tests` are pre-existing and not from
this change -- `test_no_new_bare_str_language_fields`, `test_no_surplus_kwargs`
(a surplus `page_size` kwarg on `flows.modelo_workspace_results.page_bounded`),
and `test_translatable_instances_use_only_tr_alias_without_shadowing` (155
files binding `tr` from a non-i18n import). They scan committed source this
change does not touch. 124 passed alongside them.

