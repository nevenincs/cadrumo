---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:40adb87e138112421b39c0762ec05d1a8c9e0679df5caba1bc9eec1184970dd7'
step_id: 'S01'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

# write a byte-level test asserting the M200 open-tag composite against current output, confirmed red

## Scope

- `src/cadrumo/application/filing/tests/test_export.py`

## Description

- Author one byte-level assertion over the rendered Modelo 200 fichero, covering
  both envelope ends and the markers between them: bytes 0-16 (the 17-character
  open tag), 17-21 (`<AUX>`), 322-327 (`</AUX>`), the two EEDD header slots at
  92-95 and 100-108, and the final 18 bytes (the close tag).
- Ground every expected string on sheet `DP200000` of the bundled 2024 diseño de
  registro rather than on the registry declaration under test. That sheet prints
  its row-1 and row-13 example content literally, and the existing export fixture
  files the same ejercicio and periodo the example uses, so the expected bytes are
  AEAT's own printed strings.
- Run the assertion against the unmodified declaration and confirm the red.

## Outcome

The assertion reds on the defect itself, at the first byte of the file:

    assert b'2024             ' == b'<T200020240A0000>'
    At index 0 diff: b'2' != b'<'

That is the collapsed composite emitting the four-character year and padding the
remaining thirteen bytes of AEAT's required constant to blanks. The red confirms
the defect independently of the reference document that reported it.

The red was observed before any declaration changed and is recorded here rather
than committed: a committed red gate would break every concurrent run in this
shared tree, so the proof is the observation, not a published failing state.

## Verification

Pre-fix run, against the unmodified registry declaration:

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py::test_export_writes_the_modelo_200_envelope_tags_aeat_publishes -n0 -q
    1 failed in 13.28s

`-n0` is passed explicitly because the project's pytest configuration injects
`-n auto`, and a proof read from the controlling session must not be scattered
across worker processes.

## Notes
