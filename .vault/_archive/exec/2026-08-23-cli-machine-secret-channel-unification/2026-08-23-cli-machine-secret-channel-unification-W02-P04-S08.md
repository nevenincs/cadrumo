---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6d317903c52c32b2c27d2036b7ee6e29b19101a6888687cb0ce66771651aa3b1'
step_id: 'S08'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate passphrase rotation to the shared capability and canonical payload model

## Scope

- `src/cadrumo/entrypoints/cli/_config/_passphrase.py`

## Description

- Ground passphrase rotation in the live command, shared secure-input capability,
  closed machine-secret registry, governing ADR, and approved plan.
- Inherit the canonical frozen strict payload base and register the rotation
  payload against its declared three-field contract.
- Replace the command-local descriptor/stdin branching and compatibility
  conflict call with the shared selector and typed payload reader.
- Preserve no-echo interactive collection, proof-before-mutation ordering,
  confirmation forwarding, password policy enforcement, and secret-free output.
- Verify focused rotation integration behavior, secure-input and metadata tests,
  lint, type analysis, importability, diff hygiene, and Vault structure.

## Outcome

`config passphrase change` now consumes `--secrets-stdin` and `--secrets-fd`
through the same canonical selector and bounded reader as the migrated login and
profile-creation surfaces. Its local model remains the semantic authority for
`current_passphrase`, `new_passphrase`, and `new_passphrase_confirmation`, while
the shared base owns strict frozen validation and the closed registry proves the
model matches machine-discoverable metadata.

The obsolete direct calls to `read_secrets_fd`, `read_secrets_stdin`, and
`resolve_secrets_channel`, the repeated `BaseModel`/`ConfigDict` configuration,
and the local transport precedence branch were deleted. Rotation continues to
resolve and prove the active profile only after secret collection and mutates
only through `rotate_profile_passphrase`.

## Notes

The focused integration rotation test passed under its required `integration`
marker. Ruff, `ty`, `pyrefly`, import, secure-input, and machine-metadata checks
passed. A direct file-only basedpyright invocation reports the longstanding
private-import diagnostic for `_emit_envelope`, an untouched pre-existing line;
the change introduced no type diagnostic. No declaration tuple required editing
because the landed command specification already carries both canonical flags.

Post-landing review identified and closed one LOW narrative drift: the module
had claimed that the CLI compared confirmation locally, although it correctly
forwards both values to the application authority. The corrected comment now
describes that single authoritative comparison without changing behavior.
Focused rotation integration, Ruff, and Vault checks passed after remediation.
