---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:61d9454e1863456e98571f7daa6ac7e2fd2486593ebca08e9d1ab25c96893485'
step_id: 'S446'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give dev.locales a batch removal verb, and make it refuse the silent no-op its own batch remover allows. Deleting N keys through the single-key verb costs N interpreter starts, which turned a routine catalogue cleanup into half an hour of process startup. The plural manager method already existed and was simply unexposed; what it does NOT do is report a key it cannot find in a sharded catalogue, so a typo, a stale list or an already-applied manifest reads as success having done nothing.

## Scope

- `dev/locales/cli.py`
- `dev/locales/manager.py`
- `dev/locales/tests/test_remove_batch.py`

## Changes

18 passed. The verb exists because deleting 176 keys through the single-key
`remove` cost 176 interpreter starts -- about half an hour of process startup to
delete map entries, which the operator stopped as a suspected hang. It was not
hung. That is a defect in the tool, not a cost the work should absorb.

Most of the verb already existed. `LocaleManager.remove_locale_values` was
written, atomic, shard-aware, and simply not exposed through the CLI, so the
change is one command and a public accessor rather than new removal machinery.

WHAT THE VERB ADDS BEYOND SPEED is the part worth having. The batch remover
silently ignores a key it cannot find in a sharded catalogue -- the shipped
shape -- while the single-key verb raises for the same key. So a manifest with a
typo, a stale list, or one already applied reports success having done nothing.

That is not hypothetical here: the 176-key cleanup ran twice against a list
whose keys carried a trailing carriage return, and both runs reported 176
failures with no indication of why. Silent success would have been worse than
the loop being slow, because nothing would have said the catalogue was
unchanged.

So an absent key REFUSES by default and is named, and the refusal happens before
anything is deleted -- a batch that half-applies then fails leaves the caller
diffing the catalogue to find which half. `--ignore-missing` is the explicit
opt-in for re-running a manifest, and it still reports what it skipped rather
than folding those keys into the removed count.

Teeth on exactly the failure that cost the time: replacing the absent-key
refusal with a silent skip. The gate fails on the mixed manifest -- the batch
reports success, and the present key is gone. Restored by copy.

## Notes

The asymmetry between the two removers is left as it is. `remove_locale_value`
raises for a missing key while `remove_locale_values` skips it, and the verb
compensates by checking the catalogue before calling. Making the plural method
raise would be the deeper fix, but it is a behaviour change for every existing
caller of a shipped method, which is more than this target asked for. The
compensation is at the CLI boundary, where the operator is, and the docstring
says which layer is doing it.
