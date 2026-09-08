---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e7887ebfe312848c9db7411acf6e8980e3f602333200b3a6aedafd36039dcd09'
step_id: 'S188'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the speculative, test-only `describe_impersonation_target` production wrapper and its wrapper-only assertions, amend the governing decision so exact identity surfacing reads the canonical `GoogleImpersonationConfig.target_principal` field, and retain live credential-resolution behavior.

## Scope

- `Google impersonation adapter and focused tests`
- `Google service-account impersonation ADR`
- `exact unused-symbol detector`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/adapters/outbound/google/impersonation.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_impersonation.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py`
- `M` `src/cadrumo/entrypoints/cli/config/_google_credential_source_cli.py`
- `M` `.vault/adr/2026-07-04-google-sa-impersonation-adr.md`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/outbound/google/tests/test_impersonation.py src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py src/cadrumo/entrypoints/cli/config/tests/test_google_credential_source_cli.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/google/impersonation.py src/cadrumo/adapters/outbound/google/tests/test_impersonation.py src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py src/cadrumo/entrypoints/cli/config/_google_credential_source_cli.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`
- `verify:` `uv run --no-sync vaultspec-core vault check --feature google-sa-impersonation` -> `pass`
- `verify:` `independent S188 code review and re-review` -> `pass`
