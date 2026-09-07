---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d0c64a40c516b06b200177409a195c059daa7279001f4232b13c855b8178b60a'
step_id: 'S72'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Make an aged-out approval actually reportable now that a persisted approved draft exists: have the review queue recompute an APROBADO draft's verdict before classifying it, which reaches refresh_review_status and makes the APROBACION_CADUCADA row the adapter already knew how to emit reachable for the first time. The refresh stays in memory because these adapters are pure readers and the verdict is derived state. A/B-confirm the new case fails without the wiring, and pair it with the control against a queue that reports every approval stale.

## Scope

- `src/cadrumo/application/review/_adapters.py`
- `src/cadrumo/application/review/tests/test_adapters_approval_staleness.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/review/_adapters.py`
- `A` `src/cadrumo/application/review/tests/test_adapters_approval_staleness.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../test_adapters_approval_staleness.py` 2 passed; with the
  one wiring line reverted against a copy, the first case fails `0 == 1` and the
  control still passes
- `verify:` `pytest .../review/tests/test_adapters.py` 19 passed, no regression
- `verify:` `python -m dev.audit.unreachable_code` unused 1045 -> 1044,
  exact 417 -> 416; `refresh_review_status` no longer reported
- `verify:` `ruff check` and `ty check` clean on both changed modules

## Notes

The sibling case in `test_adapters` writes a draft that is ALREADY stale and
proves the row renders. That cannot distinguish a queue which detects staleness
from one that only repeats what it was told, which is why the new cases write an
`APROBADO` draft and require the queue to reach the verdict itself.

The refresh is deliberately not written back. The module's own docstring says
its adapters are pure readers, and the verdict is derived state: freezing it into
the store on a read would make the stored status depend on when someone happened
to open the review queue. Only `APROBADO` drafts are recomputed -- every other
status either has no basis to compare or is already downstream of approval, and
the recomputation loads catalogues and a registry snapshot.

`describe_stale_reason` was the obvious next symbol to wire and I started to,
appending rendered reason phrases to the row's summary. That was wrong and the
type surface said so: `FindingReviewItem.summary` is a `Translatable`, an
abstract i18n KEY, so concatenating rendered text into it produces a value no
catalogue can translate. Reverted. The function belongs at the presentation
boundary that renders the row, which must first carry the stale reasons as
stable tokens. Its ledger entry now records that as a understood shape rather
than an open question.
