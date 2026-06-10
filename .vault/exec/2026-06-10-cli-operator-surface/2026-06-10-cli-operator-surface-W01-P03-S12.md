---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
step_id: 'S12'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# implement the highest feasible D6 outcome in ordering work-then-remove-then-warn: make --language localize help text if the spike succeeds, else remove it from the help surface it cannot affect, else emit a one-line warning naming AEAT_OUTPUT_LANGUAGE

## Scope

- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/_language_argv.py`

## Description

- Add `_language_argv.py` owning a pure, dependency-free argv pre-parse: `apply_language_argv_to_environment(argv)` reads `--language` / `--lang` (and the `=` spliced forms), normalises against the shipped locale set, and promotes a supported value to `AEAT_OUTPUT_LANGUAGE`.
- Call the pre-parse at the top of `main()`, before `app(prog_name="aeat")` dispatches and before the lazy subcommand modules render their `tr(...)`-bound help.
- Forward only supported values; leave invalid values for the canonical Typer `Choice` on the root callback so it remains the single refusal authority.

## Outcome

Implemented the **highest D6 outcome — make it work**. `--language` now genuinely localizes leaf and group subcommand help text, not just command output. An explicit flag wins over an ambient `AEAT_OUTPUT_LANGUAGE` for that run; the profile-owned precedence and the env override for flag-less sessions are untouched. No shim, alias, or deprecation surface was introduced. The flag was NOT removed (it is honest on both output and help paths now) and no warning was added (warn-only was the least-preferred residual, unnecessary once make-it-work succeeded).

The root callback's existing `override_settings(aeat_output_language=...)` is retained: it still localizes command output for the in-process `CliRunner` path that bypasses `main()`, and is harmlessly redundant with the env var on the real console.

## Notes

An invalid `--language xx` still refuses with the accepted-set hint (`'xx' is not one of 'es', 'en', 'ca', 'hu'`) because the pre-parse forwards only supported values — no silent failure on any path.
