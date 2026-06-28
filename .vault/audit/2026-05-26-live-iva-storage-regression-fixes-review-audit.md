---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` Code Review

LIVE-IVA-STORAGE-001 | INFO | Local review completed after reviewer subagent quota failure
The requested reviewer persona could not complete because the execution account hit its usage limit. A local review covered the changed storage/profile/CLI/modelo registry surfaces. No open correctness findings remain from that review. Verification completed with focused CLI/storage/modelo/profile tests, direct registry validation, ruff, and `git diff --check`.

LIVE-IVA-STORAGE-002 | FIXED | CLI profile tests no longer depend on root database routing
The CLI workflow fixture now uses file custody with the shared test database passphrase, clears inherited database and active-profile environment overrides, and asserts encrypted ledger payloads in the active profile bucket database. This protects the regression where profile-bound storage could accidentally pass through an explicit root database URL.

LIVE-IVA-STORAGE-003 | FIXED | Modelo export no-active-bucket refusal happens before repository construction
`export_modelo_revision` now resolves the active bucket before constructing bucket-scoped repositories, preserving the intended typed no-active-bucket error instead of leaking lower-level repository routing errors.

LIVE-IVA-STORAGE-004 | FIXED | Registry validation restored for split Modelo 303 and declaration-PDF specimen gates
The duplicate monolithic Modelo 303 registry file was removed after the split directory layout became authoritative. Declaration-PDF extraction profiles without fixture specimens now explicitly carry `provisional_pending_specimen = true` for the affected registry revisions.

LIVE-IVA-STORAGE-005 | OPEN | Broader EphemeralMasterKeyProvider default-repository backlog remains tracked
The storage hygiene guard now tracks remaining default-repository tests as an explicit backlog rather than hiding the already-fixed CLI workflow surface. The open list is recorded in the live IVA plan as `W04.F12`.
