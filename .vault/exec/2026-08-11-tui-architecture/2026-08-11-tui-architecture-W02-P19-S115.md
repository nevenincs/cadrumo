---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5f4909a25aa4fd3558b16ed9fd5c6b9f24ccec71fe53c6fd133f98c1caa37e8e'
step_id: 'S115'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Extend the immutable operation registry with OperationSchemaIdentityV1, OperationPublicDefinitionContractV1, OperationPublicContractSetV1, exact strict-model fingerprints, registered REVIEW and refresh adapters, deterministic definition digests, and contract-set fixed-point validation

## Scope

- `src/cadrumo/application/operations/_registry.py`

## Description

- Publish strict V1 schema identity, definition manifest, and contract-set models through the sole operations facade.
- Bind stable schema identities to exact strict Pydantic models and validate canonical JSON-schema fingerprints.
- Register domain-owned REVIEW projector and Workspace-refresh adapter protocols outside the serializable manifest.
- Derive definition and contract-set digests through the canonical core content-hash authority with explicitly sorted set fields.
- Validate exact definition, schema, model, projector, adapter, and contract-set coverage as a live registry fixed point.
- Consolidate credential-free request schema validation onto the same strict-model schema helper.
- Add pinned fingerprint and digest witnesses, order-independence, tamper refusal, missing-adapter, model-rebinding, duplicate-identity, and incomplete-inventory gates.

## Outcome

The immutable registry can now publish a renderer-neutral, deterministic public contract set without leaking Python names, callables, raw schemas, or domain imports into the manifest. Runtime-only registrations bind each safe identity to one exact model and the optional domain adapter protocols; registry construction rejects drift between the live operation definition and its declared public row.

Scoped Ruff passed. The registry contract suite passed 20 tests, and the broader operation, auth-definition, and profile-definition cohort passed 173 tests.

## Notes

Vaultspec RAG was run before implementation across public schema identity, definition digest, REVIEW projector, refresh adapter, and canonical hashing concepts. It found `cadrumo.core.hashing.content_hash_hex` as the existing digest authority, which this step reuses, and no competing operation public-contract implementation. The post-edit fixed-point search returned `_registry.py` as the sole operation public schema, registration, and digest authority. It also exposed the duplicated strict-schema validation in credential-free request handling; that duplicate block was deleted and both paths now share `_strict_model_json_schema`.

Production registry composition remains intentionally absent and belongs to `W02.P19.S122`; this step supplies and verifies its public contract substrate only.
