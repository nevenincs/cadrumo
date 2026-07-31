---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:f9daeaa32e29cc2c5443a3932e498e362d83b2e1fb455575f9679abe88f8687f'
step_id: 'S24'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Thread operator-declared prorrata_sector_id through ManualLedgerTransactionCommand, the manual add action and the idempotency signature, add the --sector flag on ledger add, and surface a non-blocking Notice when --input-classification is set but the bucket has no especial register entry for the row ejercicio

## Scope

- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/_actions_manual.py`
- `src/aeat/application/ledger/_actions_common.py`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Add `prorrata_sector_id` to `ManualLedgerTransactionCommand` (typed, 1-64 chars) and forbid it on INTERNAL_TRANSFER rows alongside the other tax fields.
- Map `prorrata_sector_id` through the manual add action into both the domain Transaction construction dict and the bucket-event audit payload.
- Add `prorrata_sector_id` to the `_mutation_signature` idempotency fingerprint, and add `prorrata_sector_id` plus the previously-missing `input_classification` to the `_command_matches_current` re-affirmation no-op check.
- Add the `--sector` flag on `aeat app ledger add` threading to the command.
- Close the S14 inert-flag concern: emit a non-blocking WARNING `Notice` (`ledger.add.input_classification_inert`) when `--input-classification` is set but no especial register entry applies for the row's ejercicio/sector, directing the operator to `elect-especial`.

## Outcome

An operator can tag a ledger row to a differentiated sector from the CLI, and the tag is now part of the persisted identity (proven by a same-key/different-sector idempotency-conflict test). The previously-inert `--input-classification` flag now surfaces a visible advisory instead of silently doing nothing when no especial election exists, and stays silent once especial is elected. 442 tests pass under `-n0` across the prorrata CLI, ledger action, transaction model, and encrypted repository roundtrip slices; ruff, ruff format, ty, and the 213-test CLI conformance suite are green.

## Notes

- The idempotency-signature and re-affirmation completeness fix (adding `prorrata_sector_id` and the missing `input_classification`) closes a latent no-silent-under-declaration gap the single-subject-mutation-is-idempotent-guarded rule warns about: a same-key retry that changed only that field could previously no-op and drop the new value.
- The inert Notice is WARNING severity (sets envelope status to warning, exit stays 0), consistent with the other advisory notices on the ledger surface.
