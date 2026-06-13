---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
---



# `aeat-cli-hardening` `W6 Logging` `Hashed Lookup Warning`

Closed the specific leaked-warning slice for deterministic encrypted-column
lookup keys.

- Modified: `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`
- Modified: `src/aeat/adapters/persistence/storage/crypto/_test_encrypted_columns.py`
- Modified: `2026-05-08-aeat-cli-hardening-plan.md`

## Description

`HashedLookup.compute` no longer emits a runtime warning when a caller hashes a
short plaintext key. The security constraint remains documented on the
deterministic lookup type itself, while legitimate short internal keys no
longer leak an internal storage warning into operator-visible logs or command
output.

The added storage-layer regression hashes a real short key through the actual
master-key-backed digest path and asserts no warning is emitted from the crypto
module.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/crypto/_test_encrypted_columns.py -k "short_plaintext or hashed_lookup or different_plaintexts"`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_user_cli_surface.py -k "read_only_status_commands_use_isolated_local_state"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/_test_encrypted_columns.py`
- `uv run --no-sync ruff format --check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/_test_encrypted_columns.py`
- `uv run --no-sync ty check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`

All verification commands passed.
