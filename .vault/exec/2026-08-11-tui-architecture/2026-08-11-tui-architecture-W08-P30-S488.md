---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:3b528322a3bf9ae00ab31ec72fb0b9443074a4b7eca5213c6dd330e6b8e478fb'
step_id: 'S488'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Record that the scoop packaging suite returns a different verdict run to run on this host, since one unchanged command produced a pass a timeout an error set and another pass within an hour varying only by machine load, which makes a single red from it unreadable as evidence

## Scope

- `packaging/` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. This records a property of the scoop packaging suite that
S485 did not capture, and corrects a claim I made last firing that it had.

ONE UNCHANGED COMMAND, FOUR DIFFERENT VERDICTS, WITHIN AN HOUR:

    5 passed                                 501s   (S484)
    Timeout                                    --   (`packaging/`, --timeout=1200)
    5 errors                                 496s   (scoop alone, --timeout=1500)
    5 passed                                1361s   (scoop alone, --timeout=1500)

Same suite, same arguments in the last two, no commit touching `packaging/`
between them. The only variable is machine load. The configured budget is
`timeout = 300`.

WHY THIS MATTERS MORE THAN "THE BUILDS ARE SLOW". S485 recorded the builds as
sound but over budget, which invites a reader to treat a red from this suite as
a real failure that simply needs more time. It is worse than that: the suite
returns PASS, TIMEOUT and ERROR for the same code, so a single observation from
it carries no information at all. I nearly reported the 5-error run as evidence
that the release commit had broken packaging -- the same shape as reading a
parallel run's failure list as the failing set (S473).

THE RELEASE DID NOT BREAK IT. `458bda1871 chore: release main (#672)` touched
only `.release-please-manifest.json`, `CHANGELOG.md`, three packaging
`pyproject.toml` files, `src/cadrumo/__init__.py` and `uv.lock` -- version
metadata. The suite passes 5/5 on a clean run after it.

## Notes

I CLAIMED LAST FIRING THAT THE BACKLOG ALREADY CARRIED THIS. It did not: the
backlog said "sound, over their 300s budget under normal shared load", which is
the S485 finding, not this one. Checked rather than assumed this time, and the
grep returned zero.

HOW TO READ THIS SUITE ON A LOADED HOST: a red means nothing on its own. Either
run it on a quiet machine, or run it repeatedly and treat only a CONSISTENT red
as signal. The suites do carry their own `CADRUMO-HOST-LOAD` line, which is the
first thing to read when one goes red.

UNCHANGED AND STILL THE ONLY OUTSTANDING WORK:

* THE PRUNE -- manifest prepared and verified current (S487); yours to
  authorise.
* THE EXPORT TREES -- their owner's (S472, S474, S486).
* THE TWO CUSTODY CASES -- environment-limited on this host (S479).
