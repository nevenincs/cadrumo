---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5fcd881fc7b48b21175102d755ab58a0f26b45214f5d0d35a8531d5a660bc3be'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-password-custody` audit: `S246 watchdog disarm review`

## Scope

Reviewed `W06.P12.S246` and commit `c890ecea4b` across
`_stdio_lifetime.py`, `_settings.py`, `_server.py`, and
`test_stdio_lifetime.py`. The review traced normal EOF completion, startup
failure, client death, explicit disarm, replacement by a later watchdog
generation, Windows wait and handle ownership, POSIX reparent polling, settings
cache invalidation, and the real subprocess witnesses. Production code was not
modified.

## Findings

### disarm-exit-race | high | A retired watchdog generation can still hard-exit later work

The event is consulted immediately before most exit decisions, but the check and
`_exit_on_watched_death` are not atomic with `disarm_stdio_lifetime_watchdog` or
`_new_watchdog_control`. On Windows, `_windows_wait` can receive a dead target,
observe an unset event, then race with disarm or replacement setting that event
before the old thread calls `os._exit`. On POSIX the equivalent window lies
after the interruptible wait returns and before the reparent or explicit-client
death branch calls the same exit function. The global lock protects only the
active-event pointer; no exit path revalidates under that lock that its event is
still the active generation. An old generation can therefore terminate normal
later work in an embedding host despite a successful disarm, violating the
Step's central guarantee.

Disposition: **resolved in the reviewed working state**. Every Windows target
death and confirmed-orphan decision and every POSIX reparent, explicit-client,
and confirmed-orphan decision now routes through `_exit_if_current`. That helper
holds `_watchdog_lock`, verifies identity with the exact active stop event and
checks it remains unset, then retains the lock through the non-returning hard
exit. Consequently disarm or replacement winning the lock makes the old
generation a no-op, while a genuine death decision winning the lock commits the
intended process exit without a revocation window.

The new subprocess disarm test kills the client only after it has read the
`disarmed=True` line, so it proves the ordinary ordering but cannot enter the
check-to-exit race. Generation replacement is not exercised. The bounded
Windows wait, eventual target-handle closure, interruptible POSIX and unanchored
waits, server `finally` disarm, dedicated settings-cache reset, and genuine
client-death/orphan subprocess witnesses are otherwise sound in the reviewed
change.

## Recommendations

- Make every watchdog-triggered hard-exit claim generation authority atomically:
  under `_watchdog_lock`, verify `_active_watchdog is stop` and that the event is
  not set, then retire that exact generation before leaving the critical section
  to run hooks and exit. A disarm or replacement that wins the lock must make the
  old exit impossible; an exit claim that wins establishes the intended client
  death.
- Add deterministic real-thread or subprocess witnesses for both orderings at
  the decision boundary: disarm racing a signalled target, and generation B
  replacing generation A while A's target dies. Require later work to complete
  and retain the existing genuine-hang/client-death exit witnesses.

The atomic generation-authority recommendation is satisfied. The existing real
subprocess tests prove normal disarm and genuine client-death behavior, but do
not deterministically schedule both sides of the former check-to-exit race or a
generation-A-to-generation-B replacement. Those additional schedules would be
useful defense-in-depth, but the lock-protected production invariant is direct
and complete, so this is not an open finding. No CRITICAL, HIGH, MEDIUM, or LOW
finding remains unresolved.
