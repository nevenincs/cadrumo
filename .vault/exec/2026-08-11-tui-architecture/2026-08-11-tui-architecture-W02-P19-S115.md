---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:51a46fa6b09acf117880dcdfc4ad2eade4710b63aaae8689faec501f394b42a5'
step_id: 'S115'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S115 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extend the immutable operation registry with OperationSchemaIdentityV1, OperationPublicDefinitionContractV1, OperationPublicContractSetV1, exact strict-model fingerprints, registered REVIEW and refresh adapters, deterministic definition digests, and contract-set fixed-point validation and ## Scope

- `src/cadrumo/application/operations/_registry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
- Refuse lax nested models, untyped payloads, mutable containers, secret-capable schemas, schema-shape drift, unsafe hooks or serializers, unvalidated defaults, and invalid adapters before public registration.
- Add positive and adversarial fixed-tuple, model-graph, schema-closure, digest, fixed-point, and callable-signature witnesses.

## Outcome

The immutable registry now publishes renderer-neutral deterministic contracts without exposing Python class names, callables, raw schemas, or domain imports. Runtime registrations bind every safe identity to one exact immutable model graph and reject any drift from the live operation definition.

Verification passed:

- scoped Ruff;
- scoped basedpyright: 0 errors, 0 warnings, 0 notes;
- scoped `ty check`;
- focused registry and operation-model tests: 57 passed;
- all operation tests: 192 passed;
- semantic RAG and exact declaration census: the public contract family exists only in `_registry.py`, and the reusable strict model-graph validator only in `_model_contract.py`.

## Notes

A fresh pre-commit Vaultspec RAG redeclaration audit covered identity/fingerprint, definition/contract-set, REVIEW/refresh adapter, digest-producer, and facade-ownership semantics. Exact-symbol census found the V1 types, registration, strict-schema helper, and digest producers only in `_registry.py`; the facade only re-exports them, `_model_contract.py` owns the recursive strict-model validator, and `cadrumo.core.content_hash_hex` remains the sole digest authority. No competing S115 implementation exists.

Production registry composition remains deliberately absent; it belongs to `W02.P19.S122`. The repository-wide import-hygiene gate still has one unrelated failure at `application.user_profile._custody_ports.load_profile_custody_password_material`; no S115-owned source participates in it.

The independent review identified and the final hardening resolved recursive nested-model, untyped branch, mutable annotation, fixed-tuple, secret/write-only, schema drift, serializer, computed-field, default-validation, and adapter-callability gaps. Final review found no S115 production-code blocker.

