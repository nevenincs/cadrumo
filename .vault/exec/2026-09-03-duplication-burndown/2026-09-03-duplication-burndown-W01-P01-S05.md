---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e4f544b16277021505ea61442ca34bfa84e639af1123db2ef04e06659a8aefd4'
step_id: 'S05'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Prove disposition parsing and live-clone reconciliation preserve unavailable and changed-scan failures as non-green evidence

## Scope

- `dev/audit/tests`

## Changes

- `M` `dev/audit/tests/_duplication_support.py`
- `M` `dev/audit/tests/test_duplication.py`
- `M` `dev/audit/tests/test_duplication_scan.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/audit/tests` -> `pass`

## Notes

Six gates added, closing the two deferred in `S02` plus the four this Step names.

Disposition parsing: the summary/group arithmetic identity; a classification vocabulary
membership check so an invented or missing classification cannot read as a decision the
arithmetic still counts; and an owner check, because `cluster-owned` with no `owner`
names no owner and is indistinguishable from an unreviewed group labelled to look
complete.

Live reconciliation: the multiset coverage read over the real scan, now with an explicit
non-empty guard on the parsed record so coverage cannot pass vacuously.

Unavailable evidence stays non-green: an unavailable scan carries an empty `groups`
tuple, so feeding it to the coverage read returns the same "nothing uncovered" a
genuinely covered tree gives. That false green is pinned as its own unit gate, which is
what keeps the live gate's outcome precondition from being deleted as redundant by
someone reading only the coverage arithmetic.

Changed-scan evidence stays non-green: the record may not declare FEWER groups than the
live scan observes. The direction is deliberate and matches the coverage read's existing
asymmetry -- under-declaring hides debt and fails; declaring more is a landed
consolidation the record has not yet dropped, which is progress and passes.

Teeth proven for all four record gates against isolated in-memory inputs, never by
mutating the committed record: dropping one from the summary, under-declaring
`meta.observed_groups`, an invented classification, a missing classification, a blank
owner, and a missing owner each fail; live 60 against a declared 52 fails; live 40
against a declared 52 passes.
