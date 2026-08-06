---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:06d0fed66e183afd6dd9bb69303aa0bb92f644992d00ffecc8c1ba18412ba464'
step_id: 'S332'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-E broad --help text globally not hu-localised

## Scope

- `even where parent command supports --language hu the help text remains spanish/english`
- `the --help text emission must consult active locale for option descriptions and section headers`
- `src/aeat/entrypoints/cli/`

## Description

- Assess-first: found the `tr()`-bound option descriptions already localise via the `--language` env promotion; the residual gap is the framework-owned Rich section headers, which stay English.
- Added `_localise_help_section_headers()` in the console `main()`: after the language flag is promoted, rebind the `typer.rich_utils` panel titles (`OPTIONS` / `COMMANDS` / `ARGUMENTS` / `ERRORS`) and `RICH_HELP` ("Try '... --help' for help.") to the operator's resolved output locale, so the `--help` section headers localise alongside the descriptions.
- Made the rebind invocation-scoped with no cross-invocation leak: it runs once per console process in `main()`, always sets every header to that invocation's locale, and is never reached by the in-process test runner (which does not call `main()`); real `aeat` runs are one process per invocation.
- Kept `RICH_HELP`'s `[blue]...[/]` Rich markup and `{command_path}` / `{help_option}` positional placeholders intact (`tr()` uses `%{name}` interpolation, so `{...}` tokens pass through).
- Authored 5 keys x 4 locales (genuine es/ca/hu) through the `aeat.locales` CLI.
- Added two subprocess tests: `hu` section headers differ from `en`, AND an `hu` run does not leak its localised header into a later `en` process (two separate processes prove the rebind reflects only its own invocation's locale).

## Outcome

Help section headers localise: `--language hu config auth status --help` renders the `Kapcsolók` panel title; `en` renders `Options`. Gates green: ruff, ty, `test_language_flag_help_honesty` (10), locale parity + honesty (22).

Documented known residuals, out of scope for this Step: the Click-owned `Usage:` prefix and the `--help` option's "Show this message and exit." text both come from Click's own gettext (`click.decorators`), baked into each command at import — not `typer.rich_utils` constants. Localising them cleanly through the language-apply path is not possible without a Click gettext `.mo` catalog or monkeypatching Click internals; per the coordinator's "do not fight Click's usage-label internals" ruling they are left English and recorded here as a follow-up (a one-word `Usage:` / one-line help-exit residual is a far smaller gap than untranslated panel titles).

## Notes

- Commit was gated on peer task #208 (`test_work_calculate_rejects_decimal_override`) landing its uncommitted `application.modelo.errors.calculate_text_casilla_numeric_value` locale key in the shared `.yml` files: a plain pathspec `.yml` commit would otherwise sweep that peer key under this Step's SHA, and the parity gate forbids splitting the code from its locale keys. A guarded background retry waits for the peer key to reach `HEAD` (leaving this Step's `.yml` diff clean) before pathspec-committing only the six owned files — never sweeping the peer key, and the pathspec excludes the ~52 peer-staged index files. Coordinator-adjudicated wait; apply-cached escape hatch held in reserve.
- The `ERRORS` panel title is rebound for completeness, but the `aeat` CLI intercepts most error surfaces through its own refusal decoration rather than Typer's Rich error panel, so it rarely renders; left set (harmless) without a dedicated test it cannot reliably trigger.
