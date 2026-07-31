---
tags:
  - '#adr'
  - '#aeat-restructure'
date: '2026-04-30'
modified: '2026-07-17'
body_hash: 'sha256:e474b6b62eff290794547d437aa13ff9102a55c07349875474420e7605d2e1f2'
related:
  - '[[2026-04-30-aeat-restructure-research]]'
---

# Cadrumo hexagonal architecture | (**status:** `accepted`)

## Decision

`cadrumo` is the only Python package authority. The installed human CLI remains
named `aeat`, but it resolves to `cadrumo.entrypoints.cli:main`; the command name
does not create an `aeat` import namespace or a compatibility package.

Production code is organised as a hexagonal layered system:

```text
src/cadrumo/
  core/          foundational policy and cross-cutting primitives
  domain/        tax concepts, records, calculations, and domain ports
  application/   use cases and orchestration
  adapters/      inbound parsing and outbound/persistence implementations
  entrypoints/   CLI and MCP composition surfaces
  _data/         packaged registries, terminology, and authoritative corpora
```

Spanish tax vocabulary remains canonical where it expresses the business
language: `modelo`, `casilla`, `declaracion`, `justificante`, `renta`, `iva`,
and `contribuyente` are not translated into parallel English module families.

## Dependency contract

- `core` is the innermost layer and does not import domain, application,
  adapters, or entrypoints.
- Production domain code does not import application or concrete adapters.
  Domain ports express required capabilities; adapter implementations satisfy
  them outside the domain.
- Application code coordinates domain capabilities. Concrete construction and
  current outbound wiring are allowed only where the import contract records
  the exact edge; broad or implicit layer exceptions are prohibited.
- Adapters may depend inward on application, domain, and core contracts.
  Entrypoints own external invocation and composition.
- Peer domain packages do not import each other's private internals. Shared
  policy belongs in `core`; cross-domain behaviour uses public contracts or
  explicit registration seams.
- Tests may cross boundaries to exercise real round trips, but test-only edges
  do not authorize the same dependency in production code.

The executable architecture ledger is `.importlinter`. Its contracts and exact
exception pins must agree with this decision. A new production exception needs
an explicit architectural decision; it must not disappear into a wildcard.

## Hard-cutover policy

The former `src/cadrumo` tree, root re-export modules, relocation shims, migration
helpers, and deprecated compatibility imports are not part of the architecture.
Callers use the current `cadrumo` public facades directly. Dead compatibility
code is deleted rather than assigned a future removal date.

The architecture preserves capability while removing duplicate paths:

- live AEAT reads remain available through guarded outbound adapters;
- live AEAT writes remain permanently refused by the core access policy;
- calculation and casilla authority remains registry-driven;
- sensitive persistence remains behind the encrypted storage boundary;
- user workflows enter through the current CLI and MCP application surfaces.

## Placement rules

- Pure tax rules and immutable business meaning belong in `domain`.
- Use-case sequencing, reconciliation, and workflow policy belong in
  `application`.
- Browser, AEAT, Google, LLM, parser, filesystem, SQL, and encryption
  implementations belong in the appropriate adapter package.
- Stable errors, identity primitives, classification, time, money, redaction,
  and other layer-independent policy belong in `core`.
- External commands and protocol launchers belong in `entrypoints`.
- Registry and corpus files are data authorities, not substitutes for duplicate
  Python declarations.

## Consequences

Architecture work is evaluated against the live `cadrumo` tree, import
contracts, direct-import tests, and packaging smoke tests. Migration diaries and
obsolete retention promises carry no normative force. Any ADR that still treats
`src/cadrumo`, an old module root, or a compatibility shim as current authority
must be rewritten or removed.
