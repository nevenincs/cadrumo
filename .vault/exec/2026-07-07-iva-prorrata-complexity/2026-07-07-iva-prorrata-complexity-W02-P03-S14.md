---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Surface the per-input classification declaration at the CLI and the M303 especial classification metadata

## Scope

- `src/aeat/entrypoints/cli/`
- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

- Add a typed `input_classification` field to `ManualLedgerTransactionCommand` (`src/aeat/application/ledger/_models.py`) and forbid it on INTERNAL_TRANSFER rows (it is a tax-relevant field), mirroring the S04 `art_104_tres_exclusion` treatment.
- Add the `--input-classification` option to the `aeat app ledger add` verb (`src/aeat/entrypoints/cli/_ledger.py`), typed as the `InputClassification` enum so click renders a `Choice`, and thread it into the command.
- Thread the field through the command-to-Transaction build and the `_raw_fields` replay provenance (`src/aeat/application/ledger/_actions_manual.py`) and add it to BOTH single-subject idempotency comparisons — the signature tuple and `_command_matches_current` (`src/aeat/application/ledger/_actions_common.py`) — so a same-idempotency-key retry that changes only the classification is a real change, never a silent drop.
- Author the CLI help text `cli.ledger.add.input_classification_help` in all four locales through the locale CLI (`python -m aeat.locales set`).
- Populate `input_classification` in the fully-populated command roundtrip fixture and add a dedicated assertion that it survives the JSON wire contract (`test_manual_ledger_transaction_command_roundtrip.py`).

## Outcome

The operator can now declare the LIVA art. 106 per-input use classification at ledger entry (`--input-classification`), which the S12 regime-aware aggregation consumes for especial buckets. Gates green: ruff, ruff format, ty clean on the touched files; `python -m aeat.locales scaffold --check` reports all four locales ok (parity preserved); 373 ledger application tests and 27 CLI ledger/conformance/schema tests pass.

## Notes

- No M303 registry TOML change was required. The S04 exec record confirms its "M303 metadata" was the command/CLI/idempotency/locale/fixture work; the M303 export layout already carries the `prorrata-especial` field, and `input_classification` is a per-transaction ledger axis, not a registry casilla.
- The CLI option name follows the existing operator-facing `--art-104-tres-exclusion` pattern and the typed-enum Choice discipline.
