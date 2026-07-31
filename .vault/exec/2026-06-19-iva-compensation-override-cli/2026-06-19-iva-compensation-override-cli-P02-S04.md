---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:4f29390f36febcc8f3053e3279c9b1f0dd19be6c47d05b1b5f215d354b6616bc'
step_id: 'S04'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Register the iva-wallet override Typer verb with --filing-year --period --amount --reason --evidence-locator and mandatory default-off --confirm, refusing to overrule a fresh AEAT wallet decision

## Scope

- `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`

## Description

- Register the `override` Typer verb under the `iva-wallet` CLI group, mirroring the seed and correct verbs.
- Accept `--filing-year`, `--period`, `--amount`, `--reason`, `--evidence-locator`, and a mandatory default-off `--confirm`.
- Resolve the active bucket, drive the S01 recorder, and emit the standard CLI envelope reporting the recorded override and decided authority.
- Refuse to overrule a fresh AEAT wallet decision via the recorder's fresh-wallet guard.

## Outcome

- `aeat app modelo iva-wallet override` records the taxpayer override and returns the override envelope; it refuses without `--confirm` and with a blank evidence locator.
- Verified green by the CLI conformance suite and the documented-command conformance gate for the verb.
- The verb contacts AEAT zero times.

## Notes

- The verb implementation was present at HEAD; this Step verified it against real gates and closed it with an execution record.
