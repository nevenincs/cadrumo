---
tags:
  - "#adr"
  - "#live-obligations-sync"
date: 2026-04-21
related:
  - "[[2026-04-21-live-obligations-research]]"
  - "[[2026-04-12-status-reader-adr]]"
---

# Architecture Decision Record: Live AEAT Obligations & Balances Sync Engine

## Context

We are implementing the "Live AEAT Obligations & Balances Sync Engine" (Issues #169 and #171). This engine will use the existing authenticated Cl@ve session (provided by `BrowserSession` and `CertificateBackend`) to detect 'missing filings' (obligaciones) and track carried-over VAT balances (saldos de IVA a compensar).

Crucially, this logic is operating in a live-connected domain where any state-mutating requests (writes/submissions) are strictly banned by Charter #116.

## Decision

We will build library backends strictly adhering to read-only patterns:

1. **Extraction Interfaces**: We will extend the existing `StatusReader` (`src/aeat/status/_reader.py`) with two new asynchronous methods: `fetch_obligaciones_pendientes()` and `fetch_saldos_iva()`. This maintains cohesion with the current reading workflows.
2. **HTML/JSON Parsing Strategy**: Parsers will be isolated into `src/aeat/status/_parsers/obligaciones.py` and `src/aeat/status/_parsers/saldos.py`. They will consume Playwright page contents and output strict `pydantic v2` frozen models (`ObligacionPendiente` and `SaldoIva`) identical to how `Expediente` records are handled.
3. **Local Caching & Sync**: The `StatusCache` will be utilized to cache responses from the Sede to prevent excessive polling. The cache keys will be generated similarly to the existing `make_cache_key` logic using `AeatStatusKind.CALENDARIO` for obligations.
4. **Strict Anti-Write Architectural Guards**:
   - All HTTP interactions will be `GET` requests or explicitly permitted, idempotent, search-only `POST` queries.
   - The parsers and readers will never interact with form submission logic other than strictly for filtering table views.
   - The CLI module will not register any commands that can submit these forms. Any state update detected in the HTML that could accidentally lead to an AEAT write will be hard-failed and rejected before execution.

## Consequences

- **Positive:** We ensure Kent's journey remains safe from accidental submission while gathering crucial data regarding his missing obligations and carried-over VAT balances.
- **Negative:** If Sede Electrónica changes the HTML structure for "Mis Obligaciones" or VAT balances, the parsers will fail and need updating.
- **Safety:** The anti-write mandate is fully enforced by keeping this logic in `StatusReader` which lacks access to the `SubmissionEngine` context.
