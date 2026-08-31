---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f38257246392f3ac38fae98f18b3ec15f166fbb51872e58d8aa2b156f0f8c25f'
step_id: 'S152'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Hunt the partial-variant class by stripping optionality and comparing what remains, and give the group label one bound both its create and patch models read

## Scope

- `src/cadrumo/application/ledger/models.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `verify:` patch accepts a 64-character group label and None, refuses 65 and 200
- `verify:` create refuses 200, as it always did
- `verify:` `pytest application/ledger/tests -k "patch or manual or group or update" -n 0 -m ""` -> pass (107)

## Notes

The currency create/patch defect suggested a whole class, so it was hunted rather
than waited for: every full model paired with its partial variant, optionality
stripped from both sides, annotations compared on what remains. A patch model
legitimately differs from its create counterpart by making every field optional,
so a diff between them is EXPECTED to be full of `| None` noise and a real change
underneath rides along unremarked.

The first run found zero pairs and reported a clean tree. That was wrong and the
reason is worth keeping: the filter accepted only classes deriving from
`BaseModel` or `OutputSchema` DIRECTLY, and the pair that motivated the scan --
`ManualLedgerTransactionCommand` and `...Patch` -- both derive from a private
shared input base. A scan that cannot see the case that inspired it will report
a clean tree with total confidence.

One real divergence survived: `group_label` was bounded at 64 on the create
command and unbounded on the patch, so a label too long to CREATE could be
applied by EDITING. Both now read one `_GROUP_LABEL_MAX_LENGTH`.

`description` looked like a second finding and is not. The patch accepts `""`
because `_normalise_optional_ledger_text` collapses a blank to `None`, which on a
patch means "not changing this field" rather than "set it to empty".

The bound sits on the `str` arm rather than on the union. A length constraint
applied to `str | None` is asked to measure `None` and raises -- it surfaced as a
TypeError in eleven unrelated tests rather than as a message about this field.
