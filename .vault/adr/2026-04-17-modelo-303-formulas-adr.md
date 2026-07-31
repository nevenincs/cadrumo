---
tags:
  - '#adr'
  - '#modelo-303-formulas'
date: '2026-04-17'
modified: '2026-07-17'
body_hash: 'sha256:fbe2b1f47fbc8e9ac1d71cd7f79d60001f4a0ea6d466c5e67383e729f13991a1'
related:
  - '[[2026-04-17-modelo-303-casilla-rules-research]]'
  - '[[2026-04-17-modelo-formulas-adr]]'
  - '[[2026-05-19-spanish-stem-terminology-authority-adr]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
---

# Modelo 303 formula authority | (**status:** `accepted`)

## Decision

Modelo 303 calculation is registry-driven. Revision TOML beneath
`src/cadrumo/_data/registry/aeat/modelos/303/` declares the casillas,
calculation links, legal references, and effective revision. The loader and
typed calculation substrate beneath
`src/cadrumo/domain/calculations/registry/` are the only formula authority;
builders, CLI commands, and adapters may consume that authority but may not
redeclare formula tables.

Invoice tax treatment uses the Spanish-stem IVA domain. Callers use
`cadrumo.domain.iva.IvaInvoiceClassification`,
`IvaInvoiceClassificationCriteria`, and the year-keyed `IvaCatalogue` resolved
by effective date. The former English `domain.vat` package, VAT-prefixed
classification types, and singleton catalogue are absent. There is no alias,
shim, dual registry, or fallback read path for them.

## Invariants

- Every computed Modelo 303 casilla is traceable to the selected registry
  revision and its bundled legal references.
- Formula dependencies form an acyclic, typed graph and are evaluated by the
  shared calculation engine.
- The effective filing period selects both the Modelo revision and IVA
  catalogue. Callers cannot pin a process-global 2025 singleton.
- IVA direction, rate, exemption, reverse-charge, intra-community, OSS/IOSS,
  and recargo-equivalencia decisions remain typed domain evidence; they are
  not inferred in presentation or CLI code.
- Verification rejects missing operands, unknown casillas, unresolved legal
  references, and registry/classification disagreement instead of substituting
  a permissive value.

## Consequences

Modelo 303 retains its complete calculation and legal-grounding capability
while using the current `cadrumo`, `iva`, and registry authorities. New periods
extend registry data and the year-keyed IVA catalogue; they do not introduce
parallel Python rulesets or compatibility names.
