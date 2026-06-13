---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S12
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S12`

Renamed the active-profile pointer filename constant from
`active-bucket` to `active-profile` to align the on-disk file name
with the operator-facing vocabulary mandated by the
2026-05-16 ADR. The storage-layer `bucket` noun survives only
inside code identifiers (`BucketPointer`, `bucket_id` field) where
engineers — not operators — read it.

- Modified: `src/aeat/application/workflow/_bucket_pointer_io.py`
- Modified: `src/aeat/application/workflow/_bucket_pointer.py`

## Description

The filename constant `_POINTER_FILENAME` flipped to
`"active-profile"`. The module docstrings on both
`_bucket_pointer_io.py` and `_bucket_pointer.py` were updated to
match — the file lives at `<aeat-root>/active-profile` and feeds
the active-profile precedence chain. The `BucketPointer` pydantic
record's `bucket_id` field name is unchanged; the storage-layer
identifier remains a `bucket_id` inside the typed record because
the encrypted slice it points at is internally a bucket. Only the
file name and the operator-visible language flip; no record-schema
change, no migration step.

## Tests

`uv run --no-sync pytest src/aeat/application/workflow/test_bucket_pointer_io.py src/aeat/application/workflow/test_bucket_pointer.py -x -q` → 15 passed. No test referenced the old filename literal.
