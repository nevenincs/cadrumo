---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:a44c95b76e709b50b71f77dab02822b5e53bb0d79ba1786af78dbc52254e2325'
step_id: 'S199'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

## Changes

- `M` `.vault/adr/2026-08-15-profile-password-custody-per-profile-recovery-mnemonic-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/adapters/persistence/storage/recovery_key.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_recovery_key_codec.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/recovery_key.py src/cadrumo/adapters/persistence/storage/tests/test_recovery_key_codec.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" src/cadrumo/adapters/persistence/storage/tests/test_recovery_key_codec.py src/cadrumo/application/user_profile/tests/test_recovery_enrollment_at_creation.py src/cadrumo/application/user_profile/tests/test_recovery_custody.py` -> `pass (38 passed)`
- `verify:` `rg -n "decode_mnemonic|_WORD_TO_INDEX" src docs --glob '!*.pyc'` -> `pass (zero residue)`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `findings (61 unreachable modules; 895 unused symbols; 18 orphan tests)`
- `verify:` `uv run --no-sync vaultspec-core vault check all --json` -> `fail (persistent unrelated vault-wide hygiene findings; changed ADR has no reported diagnostic)`

## Notes

Vaultspec RAG search and index-status endpoints returned execution errors, so grounding used the skill's exact-search fallback, whole-file inspection, and full reads of the two accepted recovery-mnemonic ADRs. The accepted four-name codec prescription contradicted the live opaque-mnemonic custody flow and was amended in place before code removal. The canonical encoder is now tested against the external BIP-39 zero-entropy vector rather than its deleted inverse. Vault-wide checking remains red on pre-existing unrelated annotation, markdown, schema, and historical document findings; it reports no diagnostic for the amended ADR.
