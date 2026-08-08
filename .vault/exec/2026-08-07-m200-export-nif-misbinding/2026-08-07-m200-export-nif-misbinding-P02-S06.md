---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e246f61eb2e9f463ce5e7637d798028f01da7aca41adbf352674b121e650941f'
step_id: 'S06'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Name the new width check as the slot-width sibling of the overlap check in the module docstring

## Scope

- `src/cadrumo/domain/calculations/registry/_export.py`

## Description

- Name the slot-width check as the sibling of the byte-range overlap check, from both ends.
- Record in the module docstring that the two run at different times, and why that matters.

## Outcome

The overlap check's docstring in
`src/cadrumo/domain/calculations/registry/_export.py` now names the width check
and where it lives, and the width check's own module docstring names the overlap
check in return. The Step row scopes only the first module; cross-referencing both
ends was necessary because the two checks ended up in different modules, and a
one-way pointer would leave a reader arriving at the width check with no route
back.

Both pointers were repointed after the width check was extracted into
`_validate_export_field_widths.py` under the reviewability ceiling, so neither
names the module the check briefly passed through.

The module docstring of the width validator states the distinction the pair turns
on.
Overlap asks whether two fields claim the same bytes; width asks whether the bytes
one field claims can hold what that field supplies. Neither can check that a
slot's MEANING matches the published record design, which remains unswept, but a
width contradiction is detectable with no reference to that design at all.

It also records the timing difference plainly: the width check runs at registry
build over every revision, the overlap check at layout resolution. A reader who
assumed both ran together would draw the wrong conclusion about what the corpus
has been checked against.

## Verification

    uv run --no-sync ruff format --check (the six changed files)
    6 files already formatted

    uv run --no-sync ruff check (the six changed files)
    All checks passed!

## Notes

None.
