---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:979872d884ab18fb9c1b75642a1cfb4f14f589b730cdb9de72bd8a6af0c9530d'
step_id: 'S324'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the TUI process entry point that the module-execution and console-script rows both delegate to but which no row owns: the architecture decision record specifies that module execution imports the launcher's `main` directly and that packaging adds a console entry point targeting it, but the launcher exposes only composition scopes and defines no `main` at all, and there is no root application module. Construct and run the root application the navigation-composition row creates, resolving its composition scopes, so that module execution and an installed console script both have a real symbol to target -- today they would point at a name that does not exist and would raise on invocation. This Step is a prerequisite for both the module-execution delegation and the console-entry-point rows; neither can be built before it. Prove it by running the entry point itself rather than by importing the symbol, since an entry point that imports cleanly and fails to start is the defect this Step exists to prevent

## Scope

- `the TUI launcher's entry function`
- `the root application module it runs`
- `and a proof that exercises the entry point rather than importing it`

## Changes

- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `A` `src/cadrumo/entrypoints/tui/app.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py -m unit -n0` -> `pass`

## Notes

The root mounts no area. Every non-Modelo area exposes a Textual application
rather than a mountable screen, and the Modelo area, which does expose
screens, is held by its own cohort gate. The root states that condition on
screen rather than offering navigation to a destination that does not exist.

`app.py` is the navigation-composition Step's scoped file, created here in
minimal area-free form because the architecture record names it as the root
and a second root module would be a parallel implementation. That Step's
remaining work is composing areas into it.

The entry point ran but never terminated: `App.run(auto_pilot=...)` does not
exit when the pilot returns, unlike `run_test`, so an installed console
script would have hung the operator's terminal. Found only after a peer's
composition break was repaired, because the registry raised before the app
could start.

Production changes were carried to main inside `ccfddea81a`, an unrelated
operand-custody commit, before this Step could commit them; content verified
correct at HEAD. The test corrections landed here as `b5ba5a54d2`.

Nothing in production reaches `main` yet: the module-execution and
console-script rows are the only callers and both are unbuilt.
