---
tags:
  - '#plan'
  - '#hexagonal-port-wiring'
date: '2026-06-01'
tier: L2
related:
  - "[[2026-05-31-hexagonal-port-necessity-audit]]"
  - "[[2026-06-01-adr-state-snapshot-2026-06-01-research]]"
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

- [x] `S01` - `application/aggregation/_iva_ledger.py` — landed in commit `08ee2dac5`.
- [x] `S02` - `application/aggregation/_modelo_bindings.py` — rewire callers.
- [x] `S03` - `application/aggregation/_renta_income_ledger.py` — rewire callers.
- [x] `S04` - `application/aggregation/_renta_ledger.py` — rewire callers.
- [x] `S05` - `application/filing/_review.py` — rewire callers.
- [x] `S06` - `application/invoices/_linking.py` — rewire callers.
- [x] `S07` - `application/invoices/_queries.py` — rewire callers.
- [x] `S08` - `application/invoices/_reconciliation.py` — rewire callers.
- [x] `S09` - `application/ledger/_actions.py` — rewire callers (largest file in the cluster).
- [x] `S10` - verify every test passes for the touched modules.

### Phase `P02` - buckets port

Sites for `BucketEventHistoryRepository` and sibling concrete bucket
repositories → `BucketRepositoryProtocol` / sibling Protocols. Discover
via `rg "BucketEventHistoryRepository|BucketCatalogueRepository" src/aeat/application/ -l`.

- [x] `S11` - enumerate the call sites; produce a per-site checklist.
- [x] `S12` - rewire each site one at a time, commit per logical sub-cluster.

### Phase `P03` - invoices port

Sites for `InvoiceCatalogueRepository` → `InvoiceRepositoryProtocol`.

- [x] `S21` - enumerate the call sites.
- [x] `S22` - rewire each site one at a time.

### Phase `P04` - modelos port

Sites for `WorkUnitCatalogueRepository`, `CalculationRevisionCatalogueRepository`,
`ModeloRecordCatalogueRepository`, `VerificationReportCatalogueRepository`
→ Protocols defined in `domain/modelos/_protocols.py`. This is the
largest port surface — `application/modelo/_actions.py` is 4000+ lines
and a concurrent-campaign hotspot. Explicit-path staging is mandatory.

- [x] `S31` - enumerate the call sites; produce a per-site checklist.
- [x] `S32` - rewire each site, one logical sub-cluster per commit.

## Wave `W02` - verification

- [x] `S41` - `pytest src/aeat/application/ -q` — all green after each rewiring commit.
- [x] `S42` - vaultspec-rag query "application layer concrete repository type hint" should return zero hits after the wave.
- [x] `S43` - update `.vault/audit/2026-05-31-hexagonal-port-necessity-audit.md` with a closing note confirming the drift is resolved.

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
