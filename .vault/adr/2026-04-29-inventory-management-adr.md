---
tags:
  - '#adr'
  - '#inventory-management'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-inventory-management-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
---

# `inventory-management` adr: `profile ledgers for Anexo D inventory and amortization` | (**status:** `accepted`)

## Problem Statement

Kent needs persistent, multi-asset and multi-activity ledgers that derive M100
Anexo D normal values instead of forcing manual aggregate entry for inventory
variation and amortization. The design must stay compatible with existing
M100 callers and must not depend on live AEAT submission.

## Considerations

The M100 megaproject already owns the authoritative LIS art. 12.1.a table and
valuation-method enum. Duplicating those enums would create legal drift, so
profile ledgers consume them directly. #216's storage backend is now merged,
but #453's issue contract requires Path A persistence rather than making the
database a hard dependency. The security-storage audit still applies: JSON
files need schema versions and an obvious future migration path.

BOE grounding corrects one issue-text detail. Industrial buildings are 3
percent in the current LIS table, not 4 percent. Libertad de amortizacion is
implemented as an opt-in flag capped by cost basis and cited to the current
LIS structure rather than relying on the issue's art. 12.5 shorthand.

## Constraints

Models must be Pydantic v2 strict and frozen, with `extra="forbid"`.
Persistence must be JSON under the profile config root by default. Tests must
use real Pydantic instances and real temporary files, without mocks or skips.
Anexo D direct aggregate inputs must keep working. LIFO must be refused with a
clear LIS art. 17 citation before persistence.

## Implementation

Add `aeat.domain.profile.assets` with `AssetRecord`, `AmortizationLedger`,
load/save helpers, per-year amortization computation, cost-basis cap
enforcement, and Anexo D aggregate helpers. Asset records carry stable ids,
descriptions, `AssetClass`, acquisition date, cost basis, optional useful-life
override, opt-in libertad flag, optional activity allocation, and schema
version.

Add `aeat.domain.profile.inventory` with `InventoryLedger`, `MovementRecord`,
load/save helpers, movement recording, explicit LIFO parsing refusal, and
inventory variation computation. Ledgers are keyed by activity id and year.
The accepted v1 movement model derives variation from explicit closing stock
or signed movement values; full method-specific stock-layer valuation is
reserved for the continuation persistence and UX audit because it needs
opening quantities and layer detail.

Add a profile CLI namespace with `aeat profile assets` and `aeat profile
inventory` subcommands. The namespace is created locally because no existing
`aeat profile` package is present in this branch. If #452 or #454 later lands
with the same namespace, this branch should reconcile by extending the shared
namespace rather than replacing it.

Add an M100 Anexo D helper that accepts existing caller-provided inputs and
optionally overlays ledger-derived `0155` and `0173`. Ledgers win only when
explicitly passed or loadable by the caller.

## Rationale

Path A keeps #453 isolated from the storage backend even though #216 is merged.
The public profile API is a stable boundary; moving from JSON to the database
later can be done behind `load_*` and `save_*` without changing formula or CLI
callers. Keeping inventory and amortization separate mirrors their legal and
accounting nature: inventory affects variation and COGS, while long-lived
assets affect amortization and cumulative basis caps.

## Consequences

The initial M100 integration is a deterministic derivation helper rather than
a broad rewrite of the formula engine. Filing-import auto-loading can call the
same helper once import surfaces expose the right Anexo D hook. Rental
property amortization from #454 remains separate because it follows LIRPF art.
23.1.f and not LIS art. 12.1.a. Regional CCAA enrichment from #452 is deferred
because it does not change the ledger invariants.
