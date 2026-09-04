---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:79646eb60d8df469f00e95ff324023a23f3eb04de4a8bc245c4a340eb4568f55'
step_id: 'S20'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Retire the constants superseded by the file-backed master-key provider's deletion and merge the storage KDF salt length onto its one canonical home

## Scope

- `src/cadrumo/adapters/persistence/storage`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/master_key/master_key_derivation.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/records.py`
- `M` `src/cadrumo/application/user_profile/bundle_encryption.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `verify:` `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/custody src/cadrumo/adapters/persistence/storage/master_key -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail`

## Notes

The ratchet exits 1 naming two modules this Step did not touch -
`cadrumo.domain.calculations.registry._validate_parameter_temporal` and
`cadrumo.entrypoints.cli._app_ledger_command_specs` - both introduced by
concurrent peer work and both exported with test-only consumers. The two
modules this Step owns carry zero findings and their baseline entries were
removed rather than lowered.
