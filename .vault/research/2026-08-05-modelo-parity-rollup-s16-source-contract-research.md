---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:6c1eb3ce48712a729b7aa3816dfca63d0e690e4ac422ec7814f4dc401c2fa96e'
related:
  - "[[2026-08-05-modelo-parity-rollup-s16-0150-oracle-addendum-research]]"
---
# `modelo-parity-rollup` research: `S16 rental source contract`

## Scope

This evidence addendum examines the smallest source contract needed before Modelo 100 revision 2025 casilla `0150` can become a computed producer. It is limited to the persisted rental source, aggregation, secure-storage boundary, and independent oracle requirements. It does not change production code or declare the 2025 casilla computed.

## Findings

### The current persisted records do not represent the official worked example

The current rental domain exposes contract-level income and leased days through `FincaRendimientoRecord` (`src/cadrumo/domain/fincas/_models.py:225-247`), year/finca/category expense rows through `FincaGasto` (`src/cadrumo/domain/fincas/_models.py:250-273`), and a cumulative building-specific 3 percent amortization ledger through `FincaAmortizacionLedgerEntry` (`src/cadrumo/domain/fincas/_models.py:276-311`). No persisted record has a separate movable-property or furniture asset identity, in-service/disposal dates, or a contract-period allocation.

The bundled 2025 Renta manual worked example requires furniture amortization of `388.13`, deductible expenses of `2,562.91`, and reduction of `2,958.38` (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12833`). Those values cannot be reconstructed from the current persisted fields without introducing facts that the source model does not carry.

### The current aggregate is not a contract-period allocation contract

`compute_finca_aggregates` returns total rental income, expenses, building amortization, and reduction attribution (`src/cadrumo/domain/fincas/_aggregates.py:267-294`). Its expense and amortization allocation uses income-share proportions (`src/cadrumo/domain/fincas/_aggregates.py:294-311`), which is not an explicit intersection of a contract's active dates with an expense or asset-use interval. A future producer therefore needs an allocation contract that can reconcile each source amount exactly once while retaining source and contract identity.

### Secure-storage readiness is an explicit boundary

`fincas_source_readiness()` returns `ready=False` because rendimiento and amortization aggregates do not cross the canonical secure-storage revision boundary (`src/cadrumo/domain/fincas/_source_readiness.py:34-52`). Existing domain or SQL records are calculation capability, not proof that the application can resolve a calculation source with typed provenance and pull/calculate parity.

## Candidate contract questions for the ADR

The architecture decision must answer these questions without overloading the building ledger:

- Which typed asset record owns furniture basis, asset identity, in-service/disposal dates, rate provenance, and cumulative cap?
- Which canonical secure repository persists the asset, contract-use interval, and source fingerprints for the active profile bucket?
- How are income, ordinary expenses, building amortization, and furniture amortization allocated to explicit contract/date intersections, with exact reconciliation to persisted totals?
- Which single application aggregation resolver owns the source, and which `BindingSourceKind`, provenance, repeated-row identity, and calculation/pull parity does it expose?
- Which rounding stage applies to each amount, and how are non-qualifying, negative-yield, multi-contract, and partial-year cases represented?

These questions are the minimum design surface identified by the code and legal-source evidence. They are not an accepted production contract until the proposed ADR is reviewed and approved.

## Independent oracle requirements

A promotion oracle must exercise the real secure-storage-to-calculate path and independently supplied expected values for the official `2,958.38` case, a zero-reduction case, multiple contracts, partial-year boundaries, and repeated `0150` row identity. A fixture that precomputes the result or bypasses source resolution would not prove the missing contract.

## Sources

- `src/cadrumo/domain/fincas/_models.py:225-311`
- `src/cadrumo/domain/fincas/_aggregates.py:267-311`
- `src/cadrumo/domain/fincas/_source_readiness.py:34-52`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12833`
- `.vault/research/2026-08-05-modelo-parity-rollup-s16-0150-oracle-addendum-research.md`
- `.vault/audit/2026-08-05-modelo-parity-rollup-s16-s18-third-adjudication-audit.md`
- `.vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md`
