---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c9a107487e3f5c6d4a20f81b3f3a71ac32a8b5a22414f45ff6651ae8adb2e205'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W02.P19.S115 public registry review`

## Scope

Formal review of `W02.P19.S115` against accepted ADR clause D6 and the registry-API research. The review covers the V1 public schema identity, definition and contract-set manifests, runtime-only REVIEW and Workspace-refresh bindings, deterministic digest authority, fixed-point validation, facade exports, strict public-model admission, and focused tests.

## Findings

### s115-recursive-public-schema-closure | high | Strictness and closed-payload guarantees originally stopped at the outer Pydantic model

The first public-schema implementation verified `strict`, `frozen`, and `extra="forbid"` only on the outer model and did not refuse an untyped JSON-schema branch. A strict outer request could therefore admit a mutable nested Pydantic model or an `Any` payload behind a fingerprinted public identity. That violated the closed, immutable public contract required by D6.

### s115-current-strict-schema-gate | low | The first remediation required adversarial witnesses

The initial remediation delegated nested models to the reusable strict model-graph check and rejected untyped schema branches, but it did not yet prove those guarantees with focused refusal tests for lax nested models and `Any` fields.

### s115-schema-admission-hardening | resolved | Public identities now admit only exact immutable validation/serialization contracts

The completed correction preserves the canonical registry and content-hash authorities while enforcing recursive strict/frozen/extra-forbid model graphs; rejecting mutable containers and TypedDict/JSON payload bags, unvalidated defaults, computed fields, serializers, custom schema hooks, secret/write-only branches, untyped values, and open tuples or objects. Validation and serialization schemas must match exactly, and fixed tuples must declare every item and both bounds. REVIEW and refresh adapters are checked synchronously for their required arities without invocation. Focused witnesses prove each refusal and the positive closed fixed-tuple case.

### s115-final-review | resolved | No production-code blocker remains

The final independent review verified the hardened implementation and its adversarial suite. It found no remaining production-code issue; the only evidence-record defect was repaired by recreating both records through their Vault CLI scaffolds and restoring this rolling review log.

### s115-redeclaration-audit | resolved | Fresh semantic and exact-symbol census confirms one authority per S115 concern

A fresh Vaultspec RAG audit covered strict schema identities and fingerprints, public definition and contract-set fixed points, REVIEW and refresh registration, digest producers, and facade ownership. Its exact-symbol census finds all three V1 public types, runtime registrations, strict-schema validation, and both contract-digest producers only in `_registry.py`; the public facade only re-exports those types. The recursive strict operation-model graph validator exists only in `_model_contract.py`, and digesting reuses the pre-existing `content_hash_hex` authority. No duplicate or competing S115 authority was found.

## Recommendations

- No open S115 remediation remains. Preserve the focused refusal witnesses and canonical ownership boundaries when evolving public schema admission or adapter registration.
