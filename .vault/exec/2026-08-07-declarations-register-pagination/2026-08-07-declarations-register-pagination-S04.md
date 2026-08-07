---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:535f8bc33f079ba76728d88f3ff37ca8dd0cdeabf37099f1181d7a987e332d2d'
step_id: 'S04'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

The pinning test recorded the blindness and named its own reversal condition:
when a fix taught the read to reconcile against the pager's stated total, its
assertions were the ones to flip. They are flipped here, in the same change that
implements the detection, and a companion pins the case a detector could most
easily break.

## Outcome

- `tests/test_declarations_pagination_blindness.py` rewritten to three tests:
  the paginated fixture's read raises with both counts in its context; the parse
  itself stays lossless and reports the shortfall on the page; and the real
  no-pager capture reads clean and returns its rows.
- Nothing was deleted or loosened. The module docstring now states the pinned
  behaviour and keeps the record that AEAT's live pagination behaviour for this
  form is unverified.

## Verification

Three tests pass. Both cross-checks are read independently out of the raw
fixture markup — the declared total from the pager label, the rendered row count
from the grid rows — so no count is hardcoded and a regenerated fixture of a
different size travels with the assertions rather than breaking them.

Three mutations, each applied by runtime monkeypatch from a plugin outside the
repository so no tracked file was modified:

- `truncated` forced to `False`: the refusal test and the page-reporting test
  both red.
- `truncated` forced to `True`: the no-pager non-regression test reds, refusing
  the real single-row capture.
- `_parse_declared_total` forced to return `None`: the refusal test and the
  page-reporting test both red.

Both directions of error therefore fail on demand: a detector that never fires
and a detector that always fires are each caught.

## Notes

The filename still says "blindness" while the module now pins the refusal. It
was kept because the plan scopes this file by name and peers reference it; the
docstring carries the current meaning.

No live AEAT probe was run. Whether the real grid ever serves a paginated shape
for this form remains open and is not implicitly settled by this work.
