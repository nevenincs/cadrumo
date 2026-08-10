---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:664178ef98ea1e6603c08b3ff3801f7923e593e9744c0b446e24366652f623f0'
step_id: 'S04'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Define and require the exact current BucketPointer schema marker

## Scope

- `src/cadrumo/core/_bucket_pointer.py`

## Description

- Declare a named constant for the pointer document's current schema version.
- Retype the version field as a required literal pinned to that version,
  replacing a field that accepted any integer at or above one.
- Promote the constant to the module's public exports.
- Correct the class and parser docstrings, which described the version as
  starting at one rather than as pinned.

## Outcome

Landed in `aa52757` with its proof step.

The field previously accepted any integer at or above one, with no current-version
constant anywhere and no equality check. A pointer document claiming version
seven parsed clean and was returned as the active-profile default. That matters
more than the shape suggests: the pointer is the file deciding which encrypted
bucket every subsequent read and write lands in, so a document whose format
claim this code does not implement is not a value to interpret generously.

This boundary closed the omitted-marker case outright, which the profile
aggregate could not afford. The field is REQUIRED with no default, so a document
omitting the version refuses rather than inheriting the current one. That was
affordable because a census of every construction site found all of them already
passing the version explicitly, so requiring it broke nothing: the pin is
behaviourally free and removes only the accepts-anything-above-one hole.

The four production writers keep the bare literal rather than naming the
constant. The literal type enforces the value at every call site, so a future
version bump reds each writer individually and forces a conscious sweep instead
of silently retargeting them through a shared symbol.

## Notes

The census had to be redone. A substring pattern for the constructor also matches
an unrelated application-layer model of a similar name, defined locally with no
version field at all, which inflated the count and invented production writers in
another campaign's territory that do not exist. The corrected figure is 39 sites:
38 calls plus the class definition, with four production writers all inside this
campaign's own claimed territory. No external-territory site required editing, so
no own-only patch drive was needed.

The module's public exports carry the constant, but the package facade was not
touched: no cross-package consumer names it yet, and promotion is a precondition
of a consuming change rather than a speculative one.
