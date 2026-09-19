---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:dcd7990355ba73e938b845a4d90ac0c3ae952ea32e249e5e15f1f7d8f9f7dc50'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S229 M721 source-owner deferral review`

## Scope

Independent review of mixed implementation `8fda4eb1d9` and cleanup
`d69befcc5b`: BOE 2023/2024 evidence, manual casillas, threshold observations,
SOAP/export separation, the M721 model-scoped ADR, and no-runtime/no-census
boundary.

## Findings

### primary eras | low | exact BOE packages and selectors are bounded

The 2023 BOE PDF recomputes to SHA-256
`afc706b7c41a34a3cd119ea6221dc2091eac73e64669189b93d6eeed43821acb`;
the separately applicable 2024 amendment recomputes to
`27995a7285f61a3a3ff2ddd259d9b252143d2ef6fc5d999936738bbd8b116a31`.
The registry admits only `2023/0A` and `2024/0A`, refusing expansion into
2025. The eras are distinct rather than a continuity claim.

### source boundary | low | manual and threshold history remain non-substitutable

Each revision has seven manual casillas and no bindings. The existing encrypted
threshold-continuity observations retain manually supplied values; they do not
acquire complete custodian/valuation facts, durable external identity,
provenance, or absence semantics. The WSDL/XML/SOAP materials and S97-S99 export
work establish a target/serializer route only, not source acquisition. Exact
search found no M721 source-mesh resolver, source-connectivity census row,
producer, or source-owner lifecycle.

### decision boundary | low | sole accepted model-specific ADR is sound

The accepted M721 source-owner deferral ADR alone declares `ingress_blocked`
for the 2023 and 2024 annual source domains, owned by
`source-connectivity-campaign`. Its reopening predicate requires a separately
approved exact-era vertical slice, a full repeated fact semantic map, encrypted
non-lossy ownership and provenance, manual-by-design boundaries, registry and
lifecycle proof, and independent era-specific serializer proof. It does not
duplicate the existing M721 data-fidelity ADR, which remains limited to manual
threshold-continuity.

### verification | low | focused evidence is green

`uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py`
passed 7 tests. Ruff passed on that focused path. Vault checks previously report
clean structural, schema, and ADR-status gates; remaining feature warnings are
pre-existing annotations and concurrent shared work.

## Recommendations

PASS. Preserve the two exact `ingress_blocked` domains and the distinct manual
and threshold-observation paths. Reopen only after an accepted source owner
meets every era-specific ADR predicate; do not treat BOE grammar, SOAP/XML, or
serializer evidence as a source route.
