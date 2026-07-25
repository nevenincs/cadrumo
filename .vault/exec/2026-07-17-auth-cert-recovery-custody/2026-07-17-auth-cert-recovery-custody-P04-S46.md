---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S46'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Refuse in prompt_secret_no_echo when getpass cannot guarantee echo suppression, guarding the win32 sys.__stdin__ identity precondition, promoting GetPassWarning to a typed refusal, and catching OSError, proven by real-subprocess regressions

## Scope

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py`

## Description

- Read the CPython 3.13.11 `getpass.py` shipped in this project's own interpreter to
  enumerate every route to the echoing `fallback_getpass`, rather than assuming them.
- Add a win32 `sys.__stdin__` identity precondition to `prompt_secret_no_echo`, the
  exact condition `win_getpass` branches on to select the echoing fallback. POSIX is
  excluded because `unix_getpass` opens the terminal device itself.
- Promote `getpass.GetPassWarning` to an exception around the prompt call. The
  fallback emits it as its first statement, so the refusal fires before any character
  is read or displayed, covering every fallback route platform-agnostically.
- Catch `OSError` so a console-less terminal layer yields this module's own localized
  refusal rather than the generic command boundary.
- Add the `echo_suppression_unavailable` refusal message across the four locale
  catalogues through the locales CLI.
- Add real-subprocess regressions: an anti-tautology anchor proving the unguarded
  stdlib genuinely reads a planted secret through the echoing fallback, the production
  prompt refusing under the same precondition, a redirected-pipe refusal asserting the
  planted secret reaches neither stdout nor stderr, and locale-key resolution.

## Outcome

The no-echo prompt now refuses rather than degrading to a visible read. Verified
empirically on this host: with stdin rebound the guard returns
`cli.config.custody.errors.echo_suppression_unavailable`, and the anchor test confirms
the unguarded stdlib returns the planted secret through the fallback, so the refusal
is not passing vacuously.

Four new tests pass. `ruff check`, `ruff format --check`, and `ty check` clean on the
touched files. The locale suite passes 46 of 46, and the recovery-lifecycle suite
passes 5 of 5, matching its established baseline.

## Notes

Three empirical results diverged from the originating review and changed the design.

A subprocess given a pipe stdin does NOT yield `sys.stdin is not sys.__stdin__`; the
identity holds and `isatty()` is false, so the pre-existing guard already refuses. The
identity difference requires in-process rebinding by an upstream layer, which is how
the regression constructs it.

`isatty()` returns true for the Windows `NUL` device, so a character-device stdin
passes the interactive guard.

The predicted `OSError` from `msvcrt.getwch()` did not reproduce. In a
`DETACHED_PROCESS` console-less spawn, `putwch` succeeded and `getwch` BLOCKED
INDEFINITELY rather than raising. Opening the console input device does not
discriminate that state either, since it succeeds even when detached. The `OSError`
guard is retained because the gap is real in the stdlib source, but on this host the
console-less failure mode is a hang, not an exception.

Superseded in part by the following Step, which closes the hang at its real cause: the
interactive check is a false positive for a character device with no console behind
it. The console-less path is now covered by a regression that fails on timeout, so the
"not exercised" note above applies only to this Step as landed, not to the module's
current state. A timeout on the prompt was considered and rejected; detection, not
duration, was the correct layer.

The echo leak is grounded in stdlib source and in a reproduction of the fallback path
returning a planted secret. Character-level on-screen echo requires an interactive
terminal and was not observed end to end.
