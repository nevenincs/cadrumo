---
tags:
  - '#exec'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:7212713046133d90d4905a1cfe9e916554ee0715ac03593d61cbf54af756264d'
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

## Notes

- `S03` handover note is a git-ignored .tmp file in the cadrumo-agent checkout
- `S05` mirror push lists the `LOCAL_ONLY` namespace as blocked-not-skipped by design; profile schema cannot yet express a secret stored elsewhere
