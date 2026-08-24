---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:13021e3eca671104e29ab84ed4198e1bbfc9cf4483e160668b7577762b813d56'
step_id: 'S115'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Extend the immutable operation registry with OperationSchemaIdentityV1, OperationPublicDefinitionContractV1, OperationPublicContractSetV1, exact strict-model fingerprints, registered REVIEW and refresh adapters, deterministic definition digests, and contract-set fixed-point validation

## Scope

- `src/cadrumo/application/operations/_registry.py`

## Description

- Publish `OperationSchemaIdentityV1`, `OperationPublicDefinitionContractV1`, and `OperationPublicContractSetV1` through the operations facade.
- Bind each public schema identity to one exact strict Pydantic model and canonical JSON-schema fingerprint.
- Compose serializable definition contracts with runtime-only REVIEW projectors and Workspace-refresh adapters.
- Derive deterministic definition and contract-set digests through `content_hash_hex`, sorting all manifest sets before serialization.
- Validate exact definition, schema, model, projector, adapter, and contract-set coverage as a live-registry fixed point.
- Reuse one canonical recursive strict operation-model graph validator for request deep immutability and public-schema admission.
- Refuse lax nested models, untyped payloads, mutable containers, secret-capable schemas, schema-shape drift, unsafe hooks or serializers, unvalidated defaults, coercive before/plain/wrap validators, and invalid adapters before public registration.
- Add positive and adversarial fixed-tuple, model-graph, schema-closure, digest, fixed-point, and callable-signature witnesses.

## Outcome

The immutable registry now publishes renderer-neutral deterministic contracts without exposing Python class names, callables, raw schemas, or domain imports. Runtime registrations bind every safe identity to one exact immutable model graph and reject any drift from the live operation definition.

Verification passed:

- scoped Ruff;
- focused basedpyright and `ty check` on the registry-test addition: passed;
- focused registry, operation-model, and facade tests: 66 passed;
- all operation tests: 198 passed;
- semantic RAG and exact declaration census: the public contract family exists only in `_registry.py`, and the reusable strict model-graph validator only in `_model_contract.py`.

## Notes

A fresh pre-commit Vaultspec RAG redeclaration audit covered identity/fingerprint, definition/contract-set, REVIEW/refresh adapter, digest-producer, and facade-ownership semantics. Exact-symbol census found the V1 types, registration, strict-schema helper, and digest producers only in `_registry.py`; the facade only re-exports them, `_model_contract.py` owns the recursive strict-model validator, and `cadrumo.core.content_hash_hex` remains the sole digest authority. No competing S115 implementation exists.

Production registry composition remains deliberately absent; it belongs to `W02.P19.S122`. The repository-wide import-hygiene gate still has one unrelated failure at `application.user_profile._custody_ports.load_profile_custody_password_material`; no S115-owned source participates in it.

Independent review hardening resolved recursive nested-model, untyped branch, mutable annotation, fixed-tuple, secret/write-only, schema drift, serializer, computed-field, default-validation, adapter-callability, coercive before/plain/wrap validator, annotation core-schema-hook, and model-class core-schema-hook gaps. The final independent review accepted S115 with no blocker.

The final feature-scoped Vaultspec check reports no S115 defect. Its only remaining warnings belong to the concurrently scaffolded S116 record, whose template annotations and empty required sections are outside this Step's authority.
