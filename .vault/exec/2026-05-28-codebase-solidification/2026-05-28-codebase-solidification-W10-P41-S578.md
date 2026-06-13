---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S578
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S578`

Fixed incorrect marker token at `application/live/_borrador_100.py` line 304.

- Modified: `src/aeat/application/live/_borrador_100.py`

## Description

The site is a `**kwargs: Any` signature on `_derive_snapshot_id`, not a `cast()` call. The block comment previously used `CAST-RATIONALE-BORRADOR100-SNAPSHOT-DISPATCH`; replaced with `KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH` to match the sibling pattern established in W08.P36.S551 and W09.P38.S559.

## Tests

S579 extended the W9 inventory test to include `_borrador_100.py` in the `_S559_MANDATE` list, so the corrected token is now verified by `test_snapshot_dispatch_hooks_carry_kwargs_any_rationale[_borrador_100.py-_derive_snapshot_id]`. S581 adds an anti-regression test asserting the superseded token is absent. 27/27 passed.
