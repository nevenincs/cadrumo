---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `model and enum reuse`

## Scope

Audited secure-storage implementation for duplicated enums, duplicated models, duplicated constants, and missed reuse of core pydantic or settings models.

## Good Patterns

- `src/aeat/adapters/persistence/storage/runtime.py` reuses the core `StorageRouteKind` enum and route classifier instead of re-parsing database routes.
- Secure-storage payload paths consistently reuse `SensitivityClass` from core classification.
- Bucket manifests and active sessions use pydantic models for persisted and runtime state rather than ad hoc dictionaries.
- `StorageRuntimeReadinessCode`, `StorageRuntimeReadinessIssue`, `StorageRuntimeSession`, and `StorageRuntimeReadiness` are typed pydantic/enum contracts rather than plain string bags.

## Findings

- Medium: `src/aeat/application/user_profile/_profile_repository.py` duplicates Argon2id KDF defaults in `_default_kdf_params()` instead of deriving fresh manifest parameters from the canonical KDF model in `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`. This risks drift in memory cost, time cost, parallelism, output length, algorithm, or KDF version.
- Medium: secure-object namespace and schema constants are still distributed across application repositories. This remains intentionally owned by the existing `W03` namespace registry wave, but `W10` confirms the duplication pressure is real and must remain a blocking architecture concern.
- Low: lifecycle state has a mirrored enum pair, `UserProfileStatus` and `BucketLifecycleStatus`, with conversion by value in `src/aeat/application/user_profile/_profile_repository.py`. The explicit conversion is safe, but the duplicate lifecycle vocabulary should either be accepted in ADRs or consolidated through a shared model.

## Disposition

- `W11.P19.S76` owns repairing duplicated secure-storage enums and models where the audit found a concrete shared contract.
- `W03.P05` and `W03.P06` remain the architectural owner for central namespace registry work.
- `W11.P19.S77` should add guard coverage for duplicated storage constants after the namespace registry exists.

## Validation

The audit used targeted scans for repository namespace strings, schema-version constants, `SensitivityClass`, `StorageRouteKind`, pydantic models, and local `StrEnum` declarations across secure-storage and application repository code.
