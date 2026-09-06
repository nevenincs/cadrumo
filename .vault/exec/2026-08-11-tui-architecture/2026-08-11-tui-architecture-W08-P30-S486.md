---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:9fa732d5f7c5a575c3780a2d79a438361a3cd21ca0da2bc6c97bcfe589178855'
step_id: 'S486'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-verify the five named targets that are not the parity prune still hold at current head after the concurrent writers commits, and record that regenerating the export trees would leave a large uncommitted generated diff in a shared worktree which is a second reason to leave that group to its owner

## Scope

- `dev/locales`, `src/cadrumo/entrypoints/tui/modelo` (verification only)

## Changes

NOTHING WAS CHANGED. The five named targets that are not the parity prune all
hold at current HEAD: 39 tests pass, run serially.

    (1) test_locale_translation_honesty                        PASS
    (3) test_language_override_sites_match_the_sanctioned_inventory  PASS
    (4) test_required_optional_badge_keys_remain_scanner_visible     PASS
    (5) test_no_tui_module_names_the_create_action                   PASS
    (6) dev.locales remove-batch                                     PASS

Worth re-running rather than citing an earlier firing: several of these were
last confirmed many commits ago, the other writer has landed a great deal since,
and this worktree has already seen one surface reverted five times.

A SECOND REASON TO LEAVE THE EXPORT TREES ALONE, which I had not stated. S472
stopped on two grounds -- an active writer on that surface, and `m390-2022`
needing a filing-grade `_CHECK_MODE_PENDING` reason. Re-reading the first with
the worktree rules in hand, there is a plainer one: regenerating 27 trees would
leave a very large uncommitted generated diff sitting in a worktree another
contributor is actively committing from, and I do not commit. "Stage or report
only the files owned by the requested change" makes that worse than a red gate,
not better -- so the stop holds even if that writer moves on, which is not the
reasoning I gave before.

## Notes

TARGET 2 IS THE ONLY NAMED TARGET STILL RED, and only on its extras. Its missing
side has been zero since the `direction` collision resolved (S480), and every
one of the 132 extras carries a not-declared verdict from the live authority
owning its namespace (S461, S463, S482) with no dotted literal anywhere in
source (S481).

THE STANDING POSITION, unchanged and complete:

* THE PRUNE -- yours. 132 extras; the reverse-direction gate
  (`test_every_key_the_live_registry_declares_is_translated`) already protects
  against removing a key the CLI resolves.
* THE EXPORT TREES -- their owner's, for the two reasons above plus the pin.
* THE TWO CUSTODY CASES -- environment-limited on this host (S479).
* THE PACKAGING BUILDS -- sound, but over their 300s budget under this machine's
  normal shared load (S484, S485).

I have measured every test root in the repository and re-verified every gate I
closed. There is no further work here that evidence can settle.
