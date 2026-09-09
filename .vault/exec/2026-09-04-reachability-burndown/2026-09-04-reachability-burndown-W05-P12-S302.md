---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b1d51c3be9f50eff24ffb9967bfd7deefcce2a17267b6492540dfad313677ffc'
step_id: 'S302'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the text-fold detector's copied production implementation fixture while retaining its no-allowlist live-tree assertion and the canonical fold behavior owner.

## Scope

- `text-fold enrollment detector fixture`
- `focused gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/tests/test_text_fold_enrollment_inventory.py`
- `M` `src/cadrumo/adapters/inbound/notificacion/_sancion.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_pdf_rows.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_workbook.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S302.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_text_fold_enrollment_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The focused gate first exposed four live duplicate normalization implementations, then passed after all four delegated to `fold_diacritics`. The exact production detector remains red on the wider campaign findings.
