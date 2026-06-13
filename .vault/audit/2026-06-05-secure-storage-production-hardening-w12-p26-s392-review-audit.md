---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S392]]'
---

# `secure-storage-production-hardening` `W12.P26.S392` Review

## S392-001 | HIGH | Original plaintext disposition missed filed-state runtime storage

Reviewer `Pascal` found that `registry.py` wires `verify-filed-state`, which delegates
to `verify_filed_state` and loads observations through `FiledDeclaracionObservationStore`.
That store opens the active-bucket secure object repository when a repository is not
injected. The original `plaintext-exception` disposition was therefore too narrow.

Resolution: reclassify `AFR-290` as `runtime-default` with `plain-file,
secure-object, manifest-bucket` signals, and repair the CLI option surface so secure
logical observation references can reach the encrypted store.

## S392-002 | MEDIUM | CLI did not exercise secure logical observation references

The registry CLI tests exercised `verify_filed_state` directly and only checked help for
the CLI command. That left the Typer `exists=True` path validation untested for
`db://secure_objects/...` observation references.

Resolution: add CLI-level coverage that persists encrypted observations through
`FiledDeclaracionObservationStore`, invokes `app registry verify-filed-state`, and
asserts the JSON comparison result.

## S392-003 | PASS | No naked environment or exception swallowing

The module does not call `os.environ`, `getenv`, or `Settings` directly, and it does
not catch broad exceptions. The parity store default is resolved through centralized
`load_settings`. The explicit non-zero CLI exit remains limited to the registry oracle
audit's reported failures.

## S392-004 | MEDIUM | Parity tape default bypassed centralized settings

The `registry parity run` command still had a command-local `Path("var/aeat/parity")`
default for persistent parity tapes. That made the artifact root invisible to the
central settings/env inventory and inconsistent with the audit artifact storage
convention.

Resolution: add `Settings.aeat_registry_parity_store_dir`, document
`AEAT_REGISTRY_PARITY_STORE_DIR` in `env/.env.example`, and resolve omitted
`--store-root` values through `load_settings()` while preserving explicit operator
overrides.

## S392-005 | PASS | Validation

Focused ruff passed for the registry CLI module and tests. Focused filed-state CLI
tests passed with 4 selected tests. The parity settings resolver test passed directly.
The `.env.example`/`Settings` alignment tests passed. The full registry CLI integration
suite passed with 51 selected tests. JSON schema conformance passed with 41 selected
tests. Locale audit passed through `python -m aeat.locales audit`.

Reviewer note: the original high and medium findings, plus the second-pass parity
artifact settings finding, were repaired in this slice. No critical, high, medium, or
low findings remain for S392 after repair.

Disposition: close `AFR-290` as `runtime-default`.
