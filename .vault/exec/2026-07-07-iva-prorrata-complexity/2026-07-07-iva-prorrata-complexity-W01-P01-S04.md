---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-08'
step_id: 'S04'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Surface the operator exclusion declaration at the CLI and the M303 exclusion metadata in the registry

## Scope

- `src/aeat/entrypoints/cli/`
- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

- Add a typed `art_104_tres_exclusion` field to the `ManualLedgerTransactionCommand` and forbid it on INTERNAL_TRANSFER rows (it is a tax-relevant field).
- Add the `--art-104-tres-exclusion` option to the `aeat app ledger add` verb, typed as the `Art104TresExclusion` enum so click renders a `Choice`, and thread it into the command; the Transaction validator gives the instructive late refusal naming the two valid judgment members when an auto-derived value is supplied.
- Thread the field through the command-to-Transaction build and the `raw_fields` replay provenance, and add it to BOTH single-subject idempotency comparisons (the signature tuple and `_command_matches_current`) so a same-idempotency-key retry that changes only the exclusion is a real change, never a silent drop.
- Author the CLI help text in all four locales through the locale CLI.
- Populate the exclusion tag in the fully-populated command roundtrip fixture and add a dedicated assertion that it survives the JSON wire contract.

## Outcome

- Modified files: `src/aeat/application/ledger/_models.py`, `src/aeat/application/ledger/_actions_manual.py`, `src/aeat/application/ledger/_actions_common.py`, `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/application/ledger/tests/test_manual_ledger_transaction_command_roundtrip.py`, `src/aeat/locales/{en,es,ca,hu}.yml`.
- 372 ledger application tests pass; ruff / ruff-format / ty clean; locale scaffold --check reports the new key as matched (missing=0).
- Committed as one atomic change with the exec record and the plan step check.

## Notes

- M303 registry metadata: no new registry structure was needed. The M303 prorrata volume casillas (`iva.prorrata-volumen-con-derecho`, `iva.prorrata-volumen-total`) already carry `legal_refs = ["ley-37-1992:art-104", ...]`, whose `required_text` now enumerates the six art-104.Tres exclusion clauses (landed in S01). The exclusion grounding is therefore already linked from the M303 volume casillas via that legal reference; the registry needs no per-casilla exclusion field.
- Scope: only the `add` (creation) path carries the operator declaration - the load-bearing operator surface. The update/patch path is not extended in this step; the exclusion is a creation-time judgment declaration.
- The locale scaffold --check `extra` warning on es/hu (`cli.overview.warning.m303_simplificado_forfait_unavailable`) is pre-existing peer drift, not this step.
