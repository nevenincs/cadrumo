---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W18-P38-S449]]'
---

# `secure-storage-production-hardening` `W18.P38.S449` Review

## S449-001 | PASS | IVA wallet CLI delegates runtime custody

Reviewed the S449 scope as `vaultspec-code-reviewer`. `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`
uses the active bucket callback supplied by the root CLI, delegates wallet balance and
seed operations to application services, and emits typed payload envelopes. It does not
construct secure storage, inspect manifests, read raw environment variables, or parse
physical storage roots.

## S449-002 | PASS | CLI failures are localized

Help text and user-facing failures use `tr()`. Typed seed errors are converted to
localized `BadParameter` failures, decimal parse failures are surfaced, and seed
conflicts are refused instead of overwriting existing wallet state.

## S449-003 | PASS | Disposition

`AFR-301` is correctly closed as `manifest-discovery`. Runtime custody remains in the
active-bucket and IVA wallet application services below the CLI registrar.
