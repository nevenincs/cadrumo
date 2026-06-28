---
step_id: "S3"
tags:
  - "#exec"
  - "#live-iva-compensation-wallet"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
---

# live-iva-compensation-wallet #551 S3 — CLI seed help text with legal grounding

## What was done

Extended `iva_wallet_seed_cmd` help text in
`src/aeat/entrypoints/cli/_modelo.py` to distinguish:

- `--amount 0` (true first-period: legally zero per LIVA art. 99.5, Ley 37/1992)
- `--amount X` (carry-in from prior tool or AEAT-filed M303)

Updated locale files (`en.yml`, `es.yml`) to surface the same distinction in
rendered help text.

Added a CLI surface test in `test_iva_wallet_inspector.py` asserting the help
output contains `"99.5"` and either `"LIVA"` or `"Ley 37/1992"`.

## Verification gate

`aeat app modelo iva-wallet seed --help` shows the two cases with LIVA art. 99.5
cited. `pytest ...::test_cli_seed_help_text_contains_liva_art_99_legal_grounding`
passed.

## Files touched

- `src/aeat/entrypoints/cli/_modelo.py` (help text updated)
- `src/aeat/locales/en.yml` (`seed_help` key updated)
- `src/aeat/locales/es.yml` (`seed_help` key updated)
- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py` (1 test added)
