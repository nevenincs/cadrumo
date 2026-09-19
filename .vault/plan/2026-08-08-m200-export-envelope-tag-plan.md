---
tags:
  - '#plan'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_hash: 'sha256:c5eef3791d8bcc32559232e88333cf63a2fe9987fab9a2deb24b0672a5566d79'
tier: L2
related:
  - '[[2026-08-08-m200-export-envelope-tag-adr]]'
  - '[[2026-08-08-m200-export-envelope-tag-reference]]'
---
# `m200-export-envelope-tag` plan

Reconstruct the M200 fichero-BOE envelope open and close tags, a live
structural filing-correctness defect: every Modelo 200 export today omits
required AEAT literal/tag content across the whole file, not merely a
wrong-width padded field.

## Description

Executes `m200-export-envelope-tag-adr` in full. `P01` restructures the
registry TOML so the open tag composes its six literal/draft components, the
`<AUX>`/`</AUX>` markers and optional header fields render correctly, and the
missing close-tag record is added, test-first against a byte-level assertion.
`P02` closes the two registry-build gate abstentions the divergence forced
open, re-runs the fichero-BOE parity and completeness gates for M200, and
proves the regression lock with a mutation test.

## Steps

### Phase `P01` - restructure the registry TOML for byte-correct envelope tags

Restructure the M200 page-000 open tag into its six literal/draft components, promote the AUX and header filler fields, and add the missing envelope-footer record, test-first against a byte-level assertion.

- [x] `P01.S01` - write a byte-level test asserting the M200 open-tag composite against current output, confirmed red; `src/cadrumo/application/filing/tests/test_export.py`.
- [x] `P01.S02` - replace the offset-1 filing_year draft field with the six-component open-tag composite; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`.
- [x] `P01.S03` - promote the AUX and header filler fields to literal and header kind; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`.
- [x] `P01.S04` - add the envelope-footer export fragment reusing the existing computed closing-tag key; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0078-modelo-200-envelope-footer.toml`.
- [x] `P01.S05` - confirm the byte-level test goes green for both the open tag and the close tag; `src/cadrumo/application/filing/tests/test_export.py`.
- [x] `P01.S09` - add a closed-set guard test asserting no accounts-regime concept (aseguradora, entidad de credito, inversion colectiva, garantia reciproca, estado de cuentas) exists anywhere in the registry or domain model outside an explicit allowlist, so a future addition fails the gate until both hardcoded discriminante literal '0' sites are revisited together; `src/cadrumo/domain/calculations/registry/tests/test_export.py`.

### Phase `P02` - close the gate abstentions and lock the fix

Flip the filing_year and period_code canonical-width gate abstentions now that the divergence they name is fixed, run the fichero-BOE parity and completeness gates for M200, and prove the regression lock with a mutation test.

- [x] `P02.S06` - after P01 lands, flip the filing_year and period_code canonical-width gate abstentions to 4 and 2, rewriting the abstention comments to state what is now established; `src/cadrumo/domain/calculations/registry/_validate_exports.py`.
- [x] `P02.S07` - run the fichero-BOE parity and completeness gates for M200 and confirm they stay green after the restructuring; `src/cadrumo/application/filing/tests/test_export_completeness_gate.py`.
- [x] `P02.S08` - prove the byte-level test is load bearing by reverting the open-tag composite and the envelope-footer record, confirming the test reds, then restoring the fix; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`.

## Parallelization

`P02` depends on `P01` landing first: the gate abstentions cite the exact
divergence `P01` fixes, so flipping them before the registry TOML changes
would refuse the registry build. Within `P01`, Steps are sequential:
`P01.S01`'s test must be confirmed red before `P01.S02`-`P01.S04` land, and
`P01.S05` confirms green only after all restructuring Steps close.

## Verification

The plan is complete when every Step above is closed and the following all
pass:

- The byte-level open-tag and close-tag test (`P01.S01`/`P01.S05`)
  demonstrably reds against current output before the fix and passes after,
  a gate unproven until it bites.
- A mutation proof reverting either the open-tag composite or the
  envelope-footer record confirms the test flips red, then is restored green.
- The existing fichero-BOE parity and completeness gates
  (`test_export_completeness_gate.py`, `test_export_completeness_sets.py`,
  `test_fichero_boe_completeness_parity.py`, named by
  `modelo-export-mirrors-official-structure` and
  `2026-07-01-fichero-boe-parity-gate-adr`) stay green for Modelo 200 after
  `P01` lands.
- `_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS["filing_year"]` and `["period_code"]`
  gate at 4 and 2 respectively, with the registry build staying green for
  every modelo (`uv run --no-sync pytest --collect-only -q` plus the
  registry-loading suite).
- `vaultspec-core vault check placeholders` and `vaultspec-core vault plan
  check` report clean on this plan and its related documents.
