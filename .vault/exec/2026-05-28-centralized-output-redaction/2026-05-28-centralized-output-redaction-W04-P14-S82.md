---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S82'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update the CLI workflow index with the new output privacy boundary

## Scope

- `.vault/index`

## Description

- Inspected the feature index for centralized output redaction closeout coverage.
- Identified that the generated index included W04.P13 rows but not W04.P14 rows before regeneration.
- Prepared the index for regeneration through `vaultspec-core vault feature index`.

## Outcome

- `.vault/index/centralized-output-redaction.index.md` is the target index for the output privacy boundary and feature closeout.
- S79 through S82 are now documented with step records so the regenerated index can include the full W04.P14 closeout.
- `uv run vaultspec-core vault feature index --feature centralized-output-redaction` completed and regenerated `.vault/index/centralized-output-redaction.index.md`.

## Notes

- The feature index is generated content and should be refreshed through the vault CLI rather than hand-authored.
- The index command emitted an unrelated existing stem-collision warning for `2026-05-27-eu-locale-S212`; it did not block index regeneration.
