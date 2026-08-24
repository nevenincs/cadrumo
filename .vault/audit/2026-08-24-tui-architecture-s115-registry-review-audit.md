---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6b887f4c7e03e75be589f85b131420c30a59c357746489ba6ccd12ae4c746922'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W02.P19.S115 public registry review`

## Scope

Formal review of `W02.P19.S115` against the accepted operation architecture, its operation-observation research, and the approved plan row. The review covered the public V1 schema identity, definition manifest, contract-set manifest, runtime registrations, deterministic digest derivation, registry fixed point, facade exports, and the corresponding registry tests.

## Findings

### s115-recursive-public-schema-closure | high | Strictness and closed-payload guarantees stop at the outer Pydantic model

`_strict_model_json_schema` verifies `strict`, `frozen`, and `extra="forbid"` only on the top-level model, then walks its JSON schema solely for `additionalProperties` and `patternProperties`. A strict/frozen outer request type may therefore contain a default Pydantic child model: the child coerces values, ignores extras, and remains mutable, while its JSON schema contains no open-object marker and the public schema identity is accepted. The same walker accepts an `Any` field because Pydantic emits an empty property schema; this admits arbitrary untyped JSON behind an apparently closed, fingerprinted public contract. Both cases contradict the accepted requirement that public operation models are strict, frozen, and free of untyped payload bags. The focused test suite only exercises a non-strict outer type and a `dict[str, str]` open object, so it does not make this gate bite.

## Recommendations

- Before `S115` can close, make the public-schema validator prove strict/frozen/extra-forbid semantics recursively for every reachable Pydantic model and reject unconstrained JSON-schema branches such as `Any`. Add adversarial registry tests for a lax nested model, nested mutation/coercion, and an `Any` field; each must be refused before fingerprinting or binding.
- Re-run the S115 registry suite and the public-contract fixed-point tests after the validator is corrected.
