---
tags:
  - '#exec'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:bb3417e438114a852f10428ac037ab49b69e06065c6c590f3dcbe4100baf110f'
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

## Notes

- `S03` handover note is a git-ignored .tmp file in the cadrumo-agent checkout
- `S05` mirror push lists the `LOCAL_ONLY` namespace as blocked-not-skipped by design; profile schema cannot yet express a secret stored elsewhere
- `S07` enrolment in `person_acts.py` and runtime dispatch already committed in 5f7e7ee16e; S07 adds the per-action test, which fails when an action is removed from `PROVIDER_CREDENTIAL_OPERATIONS`
