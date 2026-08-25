---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:580d47c1072c5ae373bbd2a4c9d34bb24b8116bd8b21617cbfc0ec4dd4973765'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` research: `m187 payer entity iic grounding`

Modelo 187's official authorities distinguish the filer obligation from its
operation-record data.  The present source-connectivity surface has no
identified M187 carrier at either grain; the ADR must decide whether that gap
permits an existing path to be reused.

## Findings

### Article 42 RGAT is an independent obligated-person limb

Orden HAC/1417/2018 rewrites Article 2 for the 2019-and-later regime.  Besides
the withholding/payment-on-account limb, it states that persons or entities
referred to by Article 42 RGAT are also obliged to file Modelo 187.  The
canonical legal entry preserves those distinct limbs and their official
locator at `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2008`; the current
one-fact registry selector deliberately resolves only the former at
`src/cadrumo/_data/registry/aeat/modelos/187/revisions/2022-y-siguientes/applicability/0001-applicability.toml:4`.

### Type-1 and type-2 have distinct record grain

The hash-pinned 2022 AEAT record design identifies type 1 as the declarant
record and type 2 as an operation record.  Type 2 carries the declarant NIF by
reference and then operation/declared-party and IIC data; it is not a
replacement for the type-1 declarant/header identity.  The local SHA-256 is
`c7a21c1feb9619380bb0da3e73066fa3c58c628f430bf85ed9dbea15b1308eb1`, matching
the enrolled authority at
`src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml:150` and
its official AEAT URL.  The BOE layout authority similarly remains pinned at
`src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml:137`.

### Current surfaces do not identify a source carrier

The registry's four M187 summary casillas are direct manual fields at
`src/cadrumo/_data/registry/aeat/modelos/187/revisions/2022-y-siguientes/casillas/c01__c04.toml:1`.
They establish an operator entry route, not capture identity, provenance,
secure persistence, replay, review, or a source owner.  Exact repository
search finds no M187-specific source-mesh resolver, source-connectivity census
candidate, binding, or source-owned export route.  Existing resolvers remain
source-kind-specific and the temporal registry/export declarations do not
supply such a carrier.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:1989`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2008`
- `src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml:125`
- `src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml:137`
- `src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml:150`
- `src/cadrumo/_data/registry/aeat/modelos/187/manifest.toml:1`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_187/manifest.json`
- https://www.boe.es/buscar/doc.php?id=BOE-A-2018-17997
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
