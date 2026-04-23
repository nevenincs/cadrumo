---
tags:
  - "#plan"
  - "#live-obligations-sync"
date: 2026-04-21
related:
  - "[[2026-04-21-live-obligations-adr]]"
  - "[[2026-04-21-live-obligations-audit]]"
---

# Implementation Plan: Live AEAT Obligations & Balances Sync Engine

I am leveraging `vaultspec-write-plan` to dictate the implementation sequence.

## Phase 1: Models & Parsers
1. **`src/aeat/status/_models.py`:**
   - Define `ObligacionPendiente` model extending `_StatusRecord`.
   - Define `SaldoIva` model extending `_StatusRecord`.
   - Ensure both are strict `pydantic v2` frozen models with forbidden extras.
2. **`src/aeat/status/_parsers/obligaciones.py`:**
   - Implement `parse_obligaciones_pendientes(html: str) -> tuple[ObligacionPendiente, ...]`.
3. **`src/aeat/status/_parsers/saldos.py`:**
   - Implement `parse_saldos_iva(html: str) -> tuple[SaldoIva, ...]`.
4. **`src/aeat/status/__init__.py` and `_protocols.py`:**
   - Export models and define `fetch_obligaciones_pendientes` / `fetch_saldos_iva` in protocols.

## Phase 2: StatusReader Integration
1. **`src/aeat/status/_reader.py`:**
   - Add `fetch_obligaciones_pendientes` method with caching.
   - Add `fetch_saldos_iva` method with caching.
   - Guard against form submission by using strict Playwright `page.goto()` and hard-failing on explicit mutation events.
2. **`src/aeat/status/_cache_key.py`:**
   - Add parsing support for `AeatStatusKind.CALENDARIO` (obligaciones) and `AeatStatusKind.DATOS_FISCALES` / `AeatStatusKind.DEVOLUCION` (saldos).

## Phase 3: Testing & Anti-Write Guard Verification
1. **`tests/test_reader.py` or equivalent test file:**
   - Use dummy HTML to test the `StatusReader` extensions for Obligations and Balances.
   - Mock AEAT requests using Playwright interceptors or mock HTML files to verify that no mutation is attempted.
   - Enforce 100% compliance with Charter #116 (strictly read-only paths).
