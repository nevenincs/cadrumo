---
tags:
  - '#plan'
  - '#live-sync-backend'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-live-sync-backend-adr]]'
  - '[[2026-04-21-live-sync-backend-adr-audit]]'
  - "[[2026-04-21-live-sync-backend-research]]"
---
# `live-sync-backend` `phase-1` plan

Implementation of the Live AEAT Read & Sync Engine (Issues #170 and #272) based on the approved ADR.

## Proposed Changes

We will build `InboxReader` to fetch notifications and `FilingDetailScraper` to extract past filing data. The implementation strictly adheres to the read-only mandate of the `BrowserSession` and `StatusReader` (Charter #116), caching responses securely via `StatusCache`, and safely parsing Sede Electrónica HTML or PDF receipts (`justificantes`).

## Tasks

- `Phase 1: InboxReader (Issue #170)`
  1. `Step 1.1` Implement `parse_notificaciones` in `src/aeat/status/_parsers/notificaciones.py` using `BeautifulSoup`.
  1. `Step 1.2` Implement `StatusReader.fetch_notificaciones` to call the parser and utilize `StatusCache`.
  1. `Step 1.3` Wire the `aeat inbox fetch` CLI command.
- `Phase 2: FilingDetailScraper (Issue #272)`
  1. `Step 2.1` Add `pdfplumber` to project dependencies if missing.
  1. `Step 2.2` Implement PDF scraping logic for `justificante` files in `src/aeat/history/_parsers/`.
  1. `Step 2.3` Extend `HistoryFetcher` or `StatusReader` to utilize the scraper when HTML detail pages are insufficient.
  1. `Step 2.4` Wire the `aeat filing import --from-aeat` CLI command.
- `Phase 3: Testing & Validation`
  1. `Step 3.1` Write comprehensive tests with mocked HTML/JSON/PDF responses.
  1. `Step 3.2` Verify strict read-only constraints (`StatusReader` only using `GET`/`domcontentloaded`).

## Parallelization

Tasks within Phase 1 and Phase 2 can be developed in parallel as they operate on independent Sede surfaces (`Mis notificaciones` vs `Mis expedientes`). Phase 3 must run sequentially at the end of each implementation.

## Verification

Mission is successful if:
1. `aeat inbox fetch` successfully retrieves simulated notifications.
2. `aeat filing import --from-aeat` successfully extracts filing details from mock PDFs/HTMLs.
3. No Playwright `POST` or mutation methods (`.click()`, `.fill()`) are invoked in the call tree.
4. All unit and integration tests pass.
