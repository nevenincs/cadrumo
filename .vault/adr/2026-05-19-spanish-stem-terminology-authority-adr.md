---
tags:
  - '#adr'
  - '#spanish-stem-terminology-authority'
date: '2026-05-19'
modified: '2026-07-17'
related:
  - '[[2026-05-19-spanish-tax-glossary-reference]]'
  - '[[2026-07-13-cadrumo-product-rename-s64-spanish-catalogue-audit]]'
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-04-30-aeat-restructure-adr]]'
---

# Spanish tax-domain terminology authority | (**status:** `accepted`)

## Decision

Cadrumo uses Spanish stems for concepts whose meaning is defined by Spanish tax
law or the AEAT product surface. Python identifiers, registry keys, and internal
documentation use the same canonical stem so maintainers do not translate the
same concept differently at each layer.

The canonical tax-domain stems are:

- `modelo` and `casilla` for official form and field identities;
- `declaracion`, `borrador`, `justificante`, and `complementaria` for filing
  artifacts with distinct legal meaning;
- `contribuyente`, `censo`, and `apoderamiento` for taxpayer identity and
  representation concepts;
- `iva` for Spanish value-added tax concepts under Ley 37/1992;
- `renta` for Spanish income-tax concepts and `finca` for rental-property
  assets, avoiding the former `renta`/`rental` ambiguity;
- `presentado`, `descartado`, and other Spanish lifecycle values where the
  value itself represents an AEAT or statutory state.

Generic engineering concepts remain English: adapter, repository, registry,
resolver, workflow, storage, error, event, snapshot, and export are not tax
terms and must not acquire decorative Spanish aliases.

## Package and symbol authority

- The package root is `cadrumo`; Spanish terminology applies below that root.
- IVA code lives under `cadrumo.domain.iva`. A parallel `domain.vat` package,
  alias, re-export, or compatibility namespace is prohibited.
- Taxpayer domain concepts live under `cadrumo.domain.contribuyente`. A retired
  `domain.profile` package is not an alternative authority; application-level
  profile orchestration may remain under `cadrumo.application.profile`.
- Current public facades and registry definitions determine the exact symbol
  inventory. This ADR does not carry a migration ledger or reserve deleted
  class names.
- One concept has one declaration. Renaming a canonical symbol is a coordinated
  hard cut across production callers and tests, never an alias pair.

## External boundaries

AEAT-owned URLs, request fields, response fields, document labels, and protocol
tokens are preserved exactly. Renaming an internal Python symbol does not
authorize changing an AEAT wire format or legal citation.

The installed operator command remains `aeat`. That command name is a product
surface, not a Python package namespace and not an exception to the `cadrumo`
package authority.

Crypto domain-separation labels and persisted identifiers are changed only by
an explicit cryptographic or storage-format decision. A label such as
`aeat.lookup.v1` is data, not a Python import path.

## Compatibility policy

The old English tax-domain symbols and retired package paths are not supported
through deprecation aliases, import shims, dual registry keys, or read-through
translation. Pre-release obsolete shapes are deleted. Persisted formats follow
their own current-format ADRs and may not infer migration authority from this
terminology decision.

## Consequences

New domain APIs must use the canonical stems above and existing APIs must not
reintroduce retired synonyms. Tests assert current public symbols directly.
Documentation may quote an old name only when clearly identifying rejected or
historical evidence; normative examples use current `cadrumo` paths and names.
