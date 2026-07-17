---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename product authentication-session storage without reading or moving former state

## Scope

- `src/cadrumo/core/auth_session_keys.py`
- `src/cadrumo/adapters/outbound/aeat/auth/_session_store.py`
- `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`
- `src/cadrumo/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py`

## Description

- Derive AEAT browser-session logical custody beneath the canonical `.cadrumo` product root.
- Preserve provider stems, encrypted payload shape, cookies, metadata, and AEAT adapter terminology.
- Reject direct operations on former `.aeat` logical keys before repository access.
- Detect corresponding former encrypted rows before canonical reads, writes, existence checks, or deletion.
- Prove refusal preserves former bytes and creates no canonical session row.

## Outcome

All certificate and Cl@ve Móvil session key producers continue to consume the shared `aeat_auth_session_storage_state_path` authority, which now yields `.cadrumo/auth/sessions/<bucket>-<provider>.json` from `PRODUCT_IDENTITY.python_package`. The hidden product root changed; the AEAT session purpose, provider-specific filenames, encrypted namespace, cookie/protocol fields, and outbound authority package did not.

The encrypted session store now raises `FormerProductAuthSessionStateError` for direct former-key operations. For canonical keys it performs an existence-only lookup of the corresponding former key and refuses before payload validation or any new write. It never loads, moves, re-keys, deletes, or adopts the former record. Eleven focused tests passed with a fresh external Cadrumo root, including real encrypted SQL storage, strict roundtrip, four direct-operation refusals, and byte-preservation/no-new-row proof.

## Notes

The first verification attempt was blocked by the concurrently executing S19 database cut and was rerun only after its import remediation landed. S20 did not modify database code. The Step scope was narrowed through the plan CLI from a broad subsystem phrase to the four concrete implementation and test files.
