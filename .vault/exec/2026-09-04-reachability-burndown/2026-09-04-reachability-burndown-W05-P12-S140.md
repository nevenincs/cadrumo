---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:daf2af122fd416af980d1c2f3caae177c938c043d618dac4c0ba00367e0b58b8'
step_id: 'S140'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the writerless deudas partial feature and its backlog suppression end to end, including speculative domain types with no independent production consumer, so liabilities return only as a specimen-grounded pull-to-persistence-to-read slice and write-path coverage enforces a live zero target

## Scope

- `liabilities ADR`
- `deudas adapter/core/application/CLI surface and tests`
- `secure namespace wiring`
- `locale keys`
- `write-path backlog gate and aggregation`

## Changes

- `M` `.vault/adr/2026-08-07-aeat-liabilities-sanciones-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `D` `dev/quality/write_path_backlog.py`
- `D` `dev/quality/write_path_backlog.toml`
- `A` `dev/quality/write_path_coverage.py`
- `M` `dev/quality/suite.py`
- `M` `dev/audit/write_path_coverage.py`
- `M` `dev/tests/test_write_path_coverage_gate.py`
- `M` `dev/identity/tests/test_identifier_namespace_enrollment_gate.py`
- `M` `justfile`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/deudas.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_schema.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `D` `src/cadrumo/application/live/deudas.py`
- `D` `src/cadrumo/application/live/tests/test_deudas_service.py`
- `M` `src/cadrumo/application/live/tests/test_live_refusal_message_key_only.py`
- `D` `src/cadrumo/core/deuda_direccion.py`
- `D` `src/cadrumo/core/objeto_tributario.py`
- `D` `src/cadrumo/core/tests/test_deuda_direccion.py`
- `D` `src/cadrumo/core/tests/test_objeto_tributario.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part1.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_command_specs.py`
- `D` `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`
- `D` `src/cadrumo/entrypoints/cli/_app_live_deudas_command_specs.py`
- `D` `src/cadrumo/entrypoints/cli/_app_live_deudas_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_app_live_command_specs.py`
- `D` `src/cadrumo/entrypoints/cli/tests/test_live_deudas_verbs.py`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/application.yml`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/cli.yml`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/errors.yml`
- `M` `docs/how-to/check-aeat-notifications.md`
- `verify:` `uv run ruff check <focused S140 paths>` -> `pass`
- `verify:` `uv run pytest -q -n 0 --confcutdir=dev/tests -m integration dev/tests/test_write_path_coverage_gate.py` -> `pass`
- `verify:` `just check-write-path-coverage` -> `pass`
- `verify:` `uv run python -c <live command graph and namespace absence assertions>` -> `pass`
- `verify:` `uv run pytest -q <focused unit paths>` -> `fail`

## Notes

The focused detector-teeth suite passes 8 tests and the live zero-target gate is green. The normal focused unit rerun cannot execute because the shared environment is missing `charset_normalizer.api`; all 57 selected tests fail in fixture setup before their bodies run. Direct command-graph and namespace assertions pass. An earlier runnable focused pass, before the environment broke, exposed and led to correction of the S140-owned live leaf-count and namespace-sequence expectations; its remaining failures were peer-owned identifier findings and one order-sensitive namespace discovery test.
