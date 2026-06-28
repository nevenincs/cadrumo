---
tags:
  - '#adr'
  - '#live-sync-backend'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-live-sync-backend-research]]'
---

# `live-sync-backend` adr: `extraction-backends` | (**status:** `accepted`)

## Problem Statement
We need to extract past filing data and Sede Electrónica notifications (Issues #170 and #272) safely using the authenticated session provided by the new Cl@ve provider, without triggering any mutations or live submission paths (Charter #116).

## Considerations
- We must build `InboxReader` to extract notifications.
- We must build `FilingDetailScraper` to extract deep details of filings.
- `StatusReader` currently implements `fetch_expedientes` but stubs `fetch_notificaciones`.
- We need a robust parsing strategy that handles both HTML and PDF formats (for "justificantes") gracefully.
- Strict read-only mandates must be upheld.

## Constraints
- **Zero Write Policy:** Absolutely no `POST` requests that alter state or use of Playwright's `.click()`, `.submit()`, `.fill()` methods.
- The extraction mechanism must be robust against the Sede Electrónica's intermittent errors and HTML layout drift.

## Implementation
- **InboxReader:** Implemented by providing a parser (`src/aeat/status/_parsers/notificaciones.py`) for `fetch_notificaciones` in `StatusReader`. This will use `BeautifulSoup` to locate and extract notification rows, mapping them to the existing `Notificacion` Pydantic model.
- **FilingDetailScraper:** This will extend the `HistoryFetcher` and/or introduce a PDF scraping mechanism (`pdfplumber`) for `justificante` links if the HTML detail page is insufficient.
- **Caching:** Both features will utilize the existing `StatusCache` infrastructure in `StatusReader` to minimize network requests. Extracted PDF content (if used) will only be parsed in memory to return Pydantic objects; raw binaries will not be cached via `StatusCache`.
- **Architectural Guards:** All requests will strictly route through `BrowserSession.navigate` or `StatusReader._fetch_html` which only perform safe `GET` requests with `domcontentloaded`. Pagination logic must rely purely on safe query parameters; no `.click()` or simulated form submissions are permitted.

## Rationale
- `BeautifulSoup` is already successfully utilized in `parse_expedientes`, proving resilient to minor layout changes when extracting table data.
- Integrating directly into `StatusReader` allows us to leverage the existing `BrowserSession`, `CertificateBackend`, and `StatusCache` implementations.
- Enforcing structural read-only guarantees in the readers acts as defense-in-depth against accidental live submissions.

## Consequences
- Requires introducing `pdfplumber` (if not already present) for PDF parsing.
- Increases the surface area of expected HTML layouts we must support and test via fixtures.
