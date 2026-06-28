---
tags:
  - "#research"
  - "#live-sync-backend"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[aeat-access-gate.index]]"
  - "[[live-write-static-audit.index]]"
---

# Live Sync Backend Research

## 1. Overview
This research covers the integration of GitHub Issue #170 (AEAT Messages Integration) and Issue #272 (Live Past Filing Extraction) into the `aeat` library. Specifically, it maps the current state of `src/aeat/status/` and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/` and determines the architectural shape for the new extraction backends (`InboxReader` and `FilingDetailScraper`).

## 2. Existing Architecture
### `aeat.adapters.outbound.aeat.browser`
- `BrowserSession`: Manages the Playwright `BrowserContext`, incorporating stealth evasion strategies (`PlaywrightStealthEvasion`), user profile configurations, and proxy settings.
- **Health Probing**: The `navigate()` method includes automatic classification of AEAT site health (maintenance banners, WAF challenges, rate limits) via `probe_response()`.

### `aeat.status`
- `StatusReader`: A read-only driver for authenticated AEAT surfaces. It lazily creates the authenticated browser context via the injected `CertificateBackend` and `BrowserSessionLike`.
- It caches results using `StatusCache` (JSON-backed).
- Currently fully implements `fetch_expedientes`.
- Stubs exist for `fetch_notificaciones`, `fetch_devoluciones`, `fetch_borrador_irpf`, `fetch_datos_fiscales`, and `fetch_calendario`, raising `StatusReaderError("... not yet implemented")`.
- **Wire Schemas**: Defined in `_models.py` (e.g., `Expediente`, `Notificacion`, `Devolucion`), leveraging Pydantic v2 `strict=True`, `frozen=True` config.

## 3. New Extraction Backends
### InboxReader (#170)
- **Goal**: Fetch user messages ("Mis notificaciones").
- **Integration Point**: Implement `StatusReader.fetch_notificaciones`.
- **Parsing Strategy**: Use `BeautifulSoup` to parse the HTML table of the "Mis notificaciones" surface. Create a parser in `src/aeat/status/_parsers/notificaciones.py` similar to `parse_expedientes()`.
- **Schema**: Map parsed data to the existing `Notificacion` Pydantic model.

### FilingDetailScraper (#272)
- **Goal**: Extract deep details from past filings (either from the detail HTML pages or by parsing the PDF "justificante").
- **Integration Point**: Extend the existing `HistoryFetcher` in `src/aeat/history/` or create a dedicated scraper if PDF parsing is required.
- **Parsing Strategy**: If HTML pages lack complete info, `pdfplumber` will be used to parse downloaded PDF "justificantes". Otherwise, continue using `BeautifulSoup` for HTML detail pages.
- **Caching**: Implement rigorous file-backed caching to minimize repeated fetches to the same detail/PDF endpoints.

## 4. Strict Anti-Write Architectural Guards (Charter #116)
- **Method Restriction**: `StatusReader` and all new backends MUST NOT execute any Playwright methods capable of mutating state (e.g., `.click()`, `.fill()`, `.submit()`). Only `.goto(..., wait_until="domcontentloaded")` and `.content()` are permitted.
- **GET only / Safe POST**: For search forms (if any), only safe idempotent requests are permitted, strictly validated before execution.
- **No Form Submission**: The `StatusReader` enforces read-only interaction by structural design.
