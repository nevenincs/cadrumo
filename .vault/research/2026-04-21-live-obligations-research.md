---
tags:
  - "#research"
  - "#live-obligations-sync"
date: 2026-04-21
related:
  - "[[2026-04-12-status-reader-adr]]"
---

# Live AEAT Obligations & Balances Sync Engine Research

I am using the `vaultspec-code-research` skill to map how to scrape the "Obligaciones" or "Mis Expedientes" areas of Sede Electrónica in order to detect missing filings (Issue #169) and track carried-over VAT balances (Issue #171).

## Scope

The scope of this research covers how to safely retrieve "missing filings" (obligaciones pendientes) and VAT balance tracking (saldos a compensar) without mutating any state on AEAT.

## Current State

The codebase contains a `StatusReader` (`src/aeat/status/_reader.py`) class that fetches authenticated status info using `BrowserSessionLike` and `CertificateBackend`. It already has `fetch_expedientes` implemented.

However, we need a new read-only interface for:
1. `fetch_obligaciones_pendientes()`: Scraping the `Calendario` or `Obligaciones` section of AEAT for explicitly marked "missing" filings.
2. `fetch_saldos_iva()`: Extracting carried-over VAT balances for VAT tracking and rollover.

### Findings

- **Missing Filings:** `AeatStatusKind.CALENDARIO` is listed in `_models.py` but isn't wired in the `StatusReader` yet. AEAT provides a "Mis Obligaciones / Calendario" page which lists pending obligations.
- **VAT Balances:** Needs to scrape VAT rollover balances. Typically found in "Datos Fiscales" or "Mis Expedientes" (modelo 303 filings previous quarter results).

## Anti-Write Guards

- All operations must use the `StatusReader`, which guarantees `read-only` interactions via Playwright (GET requests and safe form-based search POSTs).
- The `StatusReader` explicitly blocks form submission outside of search/pagination actions.
- As per Charter #116, NO default write paths can be introduced.

## Output

This research confirms we must extend `StatusReader` and introduce `_parsers/obligaciones.py` and `_parsers/saldos.py` while ensuring strict pydantic v2 wire schemas for the return types (`ObligacionPendiente`, `SaldoIva`).
