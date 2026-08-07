---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b3fa2d7e09063622907d928b5d72f8dfbf7324ff655a40a9ce50adab4c82f924'
step_id: 'S02'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Add a byte-range regression asserting the rendered page-001b offset 141 to 155 is blank for a populated profile_tax_id draft

## Scope

- `src/cadrumo/application/filing/tests/test_export_completeness_sets.py`

## Description

- Add a regression driving the real export path for a populated Modelo 200 draft and asserting the emitted bytes at the page-001B parent-TIN slot.
- Assert the declarant's own page-001 NIF slot carries the NIF, as a positive control.
- Reuse the shared byte-slice helper rather than recomputing record offsets.

## Outcome

The regression asserts the RENDERED BYTES, not the registry declaration: a test
that only checked the TOML would pass against a loader or renderer that ignored
the change. It resolves both slots through the shared byte-slice helper in
`src/cadrumo/application/filing/tests/_export_support.py`, which walks records in
declared order and accumulates record lengths, so the assertion is against
absolute payload offsets in a real exported file.

Three assertions carry it: the parent-TIN slice is exactly 15 bytes, it is all
spaces, and the declarant's NIF does not appear anywhere within it. The last is
not redundant with the second. It names the specific wrong value, so a failure
identifies the defect rather than reporting an opaque byte mismatch.

The positive control is load-bearing. A blank slice is also what a mis-addressed
slice, a draft carrying no NIF, or an export that never ran would produce.
Asserting the page-001 slot equals the draft's NIF first proves the export ran,
the harness addresses slots correctly, and a written identifier is visible
through this mechanism, so the blank below reads as a real absence.

Landed in `src/cadrumo/application/filing/tests/test_export.py` rather than the
scoped set-derivation module. That module is scoped to casilla SET derivation and
renders no bytes, while this one already owns the byte-offset idiom for this exact
modelo and layout and imports the shared helper. Adding a byte-rendering test to
the set-derivation module would have put it outside that module's declared
purpose and duplicated a harness.

## Verification

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -n0 -p no:randomly
    44 passed in 35.29s

## Notes

None.
