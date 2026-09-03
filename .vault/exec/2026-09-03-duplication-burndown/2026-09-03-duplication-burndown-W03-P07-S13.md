---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:875bf75df5bebf4d162aee0172dc73d7c7f525c23d91e027b37d22ca73674554'
step_id: 'S13'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate and resolve the three application-local clone pairs with focused invariant tests

## Scope

- `src/cadrumo/application`

## Changes

- `M` `src/cadrumo/application/export/google_operation.py`
- `M` `dev/audit/duplication_dispositions.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tests/test_google_operation.py src/cadrumo/application/export` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/export/google_operation.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`

## Notes

The three application-local pairs were adjudicated independently and reached three
different verdicts. Only one was a shared authority.

Resolved: `export/google_operation.py`. `GoogleSheetsExportRemoteResult` and
`GoogleSheetsExportOperationResult` both declared the same fourteen workbook-write facts.
That is one concept with two carriers -- the port returns the facts, the operation retains
them with provenance -- so the facts now live in a `GoogleSheetsWorkbookWriteFacts` base
both inherit. Equivalence proven by comparing pydantic field definitions before and after:
all 14 and 20 fields identical in annotation, requiredness, default and metadata, and both
models still frozen. The only schema movement is the ORDER of one `required` array; its
member set and every property definition are unchanged, and that array is a set of names
whose order carries no validation meaning.

Not consolidatable: `auth/operation_definitions.py` with `user_profile/operations.py`. The
matched span is the import preamble -- two modules that register operations importing the
same operations vocabulary. An import statement cannot be shared, and this is precisely
the phenomenon the disposition record's own banner documents: the detector flags shared
preambles while missing real semantic duplication.

Not consolidatable without merging distinct authorities:
`aggregation/_atribucion_member.py`. The self-clone spans `_observation_from_socio` and
`_detail_row_from_socio`, which build different target types and deliberately differ in
four fields: the observation renders text per the diseño (`_optional_str`, `_x_flag`)
while the row carries typed domain values (`_optional_naturaleza_inmueble`,
`_optional_situacion_inmueble`, `_optional_clave_declarado`). Merging them would couple the
source-observation contract to the domain row contract, which the governing decision
forbids.

Clone count fell from 12 to 11. Two of this Step's three groups remain in the record as
`cluster-owned` because the campaign's closure bar is a literal observed zero and neither
can honestly be classified `intentional` under that bar; see the blocked structural
residue also found in the Modelo export pair.

37 failures across the wider application selection are pre-existing. Proven by A/B on
`test_export_output_paths.py` against a copy of the unmodified module: 10 failed, 2 passed
identically with and without this change.
