---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S36'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Migrate the recovery family's risk metadata: retire `config.show_recovery` / `config.verify_recovery` rows; add `config.recovery.status` / `verify` (reads), `config.recovery.create`, and `config.recovery.rotate` (destructive - it invalidates the prior recovery code, so the MCP surface elicits confirmation).
- Update the operator-surface contract: CONFIG required children swap the retired spellings for `recovery`; one CUSTODY family mounts `status`/`create`/`rotate`/`verify`.

## Outcome

Help and risk metadata for the auth, certificate, and recovery families all cite only the accepted grammar; the curated operator help surface carried no custody entries to migrate.

## Notes

Auth and certificate rows were migrated by the earlier family cutovers; this Step's remaining delta was the recovery family.
