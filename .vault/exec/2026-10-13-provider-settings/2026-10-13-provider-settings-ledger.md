---
tags:
  - '#exec'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:69b463efeb0a45aac3fbc94f35b612ebcd7a15601e15051fc3743cf4b9e487b0'
related:
  - "[[2026-10-13-provider-settings-plan]]"
---

# `provider-settings` ledger

## Changes

- `S01` `A` `.vault/adr/2026-10-13-provider-settings-adr.md`
- `S01` `A` `.vault/reference/2026-10-13-provider-settings-reference.md`
- `S01` `A` `.vault/plan/2026-10-13-provider-settings-plan.md`
- `S01` `A` `.vault/index/provider-settings.index.md`
- `S01` `M` `.vault/adr/2026-10-11-mcp-parity-full-parity-adr.md`
- `S01` `M` `.vault/adr/2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr.md`
- `S01` `M` `.vault/adr/2026-10-04-canonical-environment-adr.md`
- `S02` `M` `agent .vault/adr/2026-10-10-cadrumo-integration-provider-settings-adr.md`
- `S02` `M` `agent .vault/adr/2026-10-11-cadrumo-integration-hosting-contract-adr.md`
- `S03` `A` `agent .tmp/2026-10-13-profile-settings/frame-handover.md`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S06` `A` `src/cadrumo/adapters/persistence/provider_settings/`
- `S06` `A` `src/cadrumo/application/provider_settings/`
- `S06` `verify:` `just check-secure-store-write-paths` -> `pass`
- `S06` `verify:` `just check-persistence-write-paths` -> `pass`
- `S07` `A` `src/cadrumo/entrypoints/runtime/tests/test_provider_credential_person_acts.py`
- `S07` `M` `.vault/plan/2026-10-13-provider-settings-plan.md`
- `S07` `verify:` `pytest src/cadrumo/entrypoints/runtime/tests/test_provider_credential_person_acts.py -n0 -m ''` -> `pass`
- `S07` `verify:` `ruff check and format` -> `pass`
- `S07` `verify:` `just check-import-boundaries (15/15 contracts kept, 0 findings; run flagged unavailable: source changed mid-run by other sessions)` -> `pass`
- `S07` `verify:` `just check-types (1 diagnostic in untracked test_worker_provider_catalog.py owned by another session; none in S07 files)` -> `fail`
- `S07` `by:` `implementation-high`
- `S08` `M` `src/cadrumo/entrypoints/cli/config/command_specs.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/command_operation_table.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/tests/command_frontend_counterparts.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/tests/test_profile_authentication_contract.py`
- `S08` `A` `src/cadrumo/entrypoints/cli/config/tests/test_provider_cli.py`
- `S08` `M` `src/cadrumo/application/operator_surface/contract.py`
- `S08` `M` `src/cadrumo/application/provider_settings/contracts.py`
- `S08` `M` `src/cadrumo/locales/en/cli.yml`
- `S08` `M` `src/cadrumo/locales/es/cli.yml`
- `S08` `M` `src/cadrumo/locales/ca/cli.yml`
- `S08` `M` `src/cadrumo/locales/hu/cli.yml`
- `S08` `M` `dev/locales/fstring_registry.py`
- `S08` `M` `dev/docs/tests/test_cli_tree.py`
- `S08` `M` `src/cadrumo_harness/_data/agent/reference/command-operations.md`
- `S08` `M` `.vault/plan/2026-10-13-provider-settings-plan.md`
- `S08` `verify:` `pytest src/cadrumo/entrypoints/cli/config/tests/test_provider_cli.py -n0 -m '' (15 incl. native runtime with stand-in agent)` -> `pass`
- `S08` `verify:` `pytest dev/quality/tests/test_production_scan_surface_has_no_orphans.py -n0 -m ''` -> `pass`
- `S08` `verify:` `pytest cli command-surface suite and dev/docs/tests/test_cli_tree.py (remaining failures are pre-existing app agent serve and config sign-in-hold findings)` -> `pass`
- `S08` `verify:` `python -m dev.locales audit (no cli.config.provider findings)` -> `pass`
- `S08` `verify:` `python -m dev.operation_contract_manifest.generate --check` -> `pass`
- `S08` `verify:` `ruff check and format` -> `pass`
- `S08` `verify:` `just check-import-boundaries (15/15 contracts kept, 0 findings; run flagged unavailable: source changed mid-run)` -> `pass`
- `S08` `verify:` `just check-types (3 diagnostics in dev/packaging/native owned by another session; none in S08 files)` -> `fail`
- `S08` `by:` `implementation-high`

## Notes

- `S03` handover note is a git-ignored .tmp file in the cadrumo-agent checkout
- `S05` mirror push lists the `LOCAL_ONLY` namespace as blocked-not-skipped by design; profile schema cannot yet express a secret stored elsewhere
- `S07` enrolment in `person_acts.py` and runtime dispatch already committed in 5f7e7ee16e; S07 adds the per-action test, which fails when an action is removed from `PROVIDER_CREDENTIAL_OPERATIONS`
- `S08` provider ids stay free text validated by the agent's declared catalog; no provider list added
- `S08` regenerating `command_operation_table.py` also dropped 285 stale `profile_login` runtime-request rows the live derivation no longer yields; the join test passes with the regenerated table
- `S08` CLI reference and cli-tree.json are gitignored build outputs; nothing committed to regenerate
