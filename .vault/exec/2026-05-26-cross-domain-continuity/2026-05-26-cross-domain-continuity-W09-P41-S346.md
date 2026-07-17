---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S346'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# R9-ANDREA-HIGH add pareja de hecho marital status option (5)

## Scope

- `closed by ec1c67cb3: RentaMaritalStatus now includes profile value PAREJA_HECHO=5 and profile binding treats code 5 / pareja_hecho_registrada as a partnered state for IRPF profile-derived facts`
- `Modelo 100 ECIVIL export remains constrained to official Estado Civil codes 1-4 and now rejects the profile-only pareja de hecho marker instead of emitting invalid XML`
- `pinned by real profile-binding and XML export tests plus the CLI marital-status round-trip coverage`
- `src/aeat/domain/user_profile/_schema.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `ec1c67cb36` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
