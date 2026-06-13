---
tags:
  - '#plan'
  - '#hexagonal-port-wiring'
date: '2026-06-01'
modified: '2026-06-01'
tier: L2
related:
  - '[[2026-05-31-hexagonal-port-necessity-audit]]'
  - '[[2026-06-01-adr-state-snapshot-2026-06-01-research]]'
  - '[[2026-06-01-domain-boundary-audit-adr]]'
  - '[[2026-06-04-hexagonal-port-wiring-adr]]'
  - '[[2026-06-04-hexagonal-port-wiring-research]]'
---

# `hexagonal-port-wiring` plan

## Wave `W01` - rewire application layer to depend on domain repository protocols

Per the 2026-05-31 hexagonal-port-necessity audit, 4 domain
`_protocols.py` files (buckets, invoices, modelos, transactions)
declare typed ports that zero application-layer callers actually use
— the application everywhere type-hints the concrete repositories
instead. This wave restores the hexagonal direction per ADR Rule 8.

The wiring is structural: each application-layer module changes its
type hints from the concrete repository class to the Protocol class.
The concrete repository continues to satisfy the Protocol by duck
typing; default-construction fallbacks remain on the concrete class
(the application is the only place that decides the concrete to
instantiate; tests inject Protocol-satisfying fakes).

Proof-of-pattern landed: commit `08ee2dac5` wires
`src/aeat/application/aggregation/_iva_ledger.py:aggregate_iva_ledger`
against `TransactionCatalogueRepositoryProtocol`. 24/24 tests stay
green; pattern verified.

### Phase `P01` - transactions port

Sites for `TransactionCatalogueRepository` → `TransactionCatalogueRepositoryProtocol`
in the application layer. Identified via
`rg "TransactionCatalogueRepository" src/aeat/application/ -l`:

- [x] `S01` - land proof-of-pattern wiring; `application/aggregation/_iva_ledger.py` (commit `08ee2dac5`).
- [x] `S02` - rewire callers; `application/aggregation/_modelo_bindings.py`.
- [x] `S03` - rewire callers; `application/aggregation/_renta_income_ledger.py`.
- [x] `S04` - rewire callers; `application/aggregation/_renta_ledger.py`.
- [x] `S05` - rewire callers; `application/filing/_review.py`.
- [x] `S06` - rewire callers; `application/invoices/_linking.py`.
- [x] `S07` - rewire callers; `application/invoices/_queries.py`.
- [x] `S08` - rewire callers; `application/invoices/_reconciliation.py`.
- [x] `S09` - rewire callers; `application/ledger/_actions.py` (largest file in the cluster).
- [x] `S10` - verify every test passes for the touched modules; `src/aeat/application/`.

### Phase `P02` - buckets port

Sites for `BucketEventHistoryRepository` and sibling concrete bucket
repositories → `BucketRepositoryProtocol` / sibling Protocols. Discover
via `rg "BucketEventHistoryRepository|BucketCatalogueRepository" src/aeat/application/ -l`.

- [x] `S11` - enumerate the call sites; bucket repository application callers.
- [x] `S12` - rewire each site one at a time; bucket repository application callers.

### Phase `P03` - invoices port

Sites for `InvoiceCatalogueRepository` → `InvoiceRepositoryProtocol`.

- [x] `S21` - enumerate the call sites; invoice repository application callers.
- [x] `S22` - rewire each site one at a time; invoice repository application callers.

### Phase `P04` - modelos port

Sites for `WorkUnitCatalogueRepository`, `CalculationRevisionCatalogueRepository`,
`ModeloRecordCatalogueRepository`, `VerificationReportCatalogueRepository`
→ Protocols defined in `domain/modelos/_protocols.py`. This is the
largest port surface — `application/modelo/_actions.py` is 4000+ lines
and a concurrent-campaign hotspot. Explicit-path staging is mandatory.

- [x] `S31` - enumerate the call sites; modelo repository application callers.
- [x] `S32` - rewire each site; modelo repository application callers.

## Wave `W02` - verification

- [x] `S41` - run application-layer tests; `pytest src/aeat/application/ -q`.
- [x] `S42` - query semantic drift; vaultspec-rag query "application layer concrete repository type hint" returns zero hits after the wave.
- [x] `S43` - record closure note; `.vault/audit/2026-05-31-hexagonal-port-necessity-audit.md`.

## Closure note -- 2026-06-01

Plan complete. All four bucket-A ports (transactions, buckets, invoices,
modelos) wired end-to-end across the application layer; three sibling
modelo Protocols (CalculationRevisionCatalogueRepositoryProtocol,
ModeloRecordCatalogueRepositoryProtocol,
VerificationReportCatalogueRepositoryProtocol) authored alongside in
`src/aeat/domain/modelos/_protocols.py`. Adoption commits enumerated in
the closure note of the related `hexagonal-port-necessity-audit`
(commits `08ee2dac5`, `39a9b1f44`, `c8c785598`, `9ba59706a`,
`cffae8d91`, `4a65a704e`, `833f57c9a`, `217b6e32f`, `e8397788a`). S43
audit closure landed in commit `c6b54c641`.
