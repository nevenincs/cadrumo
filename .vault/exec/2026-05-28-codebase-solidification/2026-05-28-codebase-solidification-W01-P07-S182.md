---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-28"
modified: '2026-05-28'
step_id: "S182"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S182 — real-behavior detection tests

## Outcome

Extended `src/aeat/adapters/inbound/financial/providers/test_detection.py` with six new
real-behavior tests in the S182 block:

- `test_csv_extensions_constant_drives_csv_provider_routing` — iterates every
  extension in `CSV_EXTENSIONS` and asserts each routes to `CsvProvider`
- `test_xlsx_extension_constant_drives_xlsx_provider_routing` — asserts `XLSX_EXTENSION` routes to `XlsxProvider`
- `test_pdf_extension_constant_returns_none_for_extension_routing` — asserts `PDF_EXTENSION` returns `None` (documented carve-out)
- `test_csv_extensions_constant_matches_csv_provider_supported_extensions` — structural invariant: `CsvProvider.supported_extensions == CSV_EXTENSIONS`
- `test_xlsx_extension_constant_matches_xlsx_provider_supported_extensions` — `XLSX_EXTENSION in XlsxProvider.supported_extensions`
- `test_pdf_extension_constant_matches_pdf_provider_supported_extensions` — `PDF_EXTENSION in PdfN26Provider.supported_extensions`

All tests pass. No mocks, no skips.

## Commit

`0ed384302`
