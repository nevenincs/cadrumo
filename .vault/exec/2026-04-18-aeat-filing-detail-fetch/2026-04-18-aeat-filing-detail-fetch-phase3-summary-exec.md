---
tags:
  - "#exec"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: exec — phase 3 summary — tests
issue: wgergely/aeat#227
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-plan]]"
  - "[[2026-04-18-aeat-filing-detail-fetch-adr]]"
---

# exec — phase 3 summary — tests

## scope executed

Plan phases 3.1–3.8.

## artefacts

- `src/aeat/status/test_models.py` — three new tests on
  `Expediente.detail_url` (default None, accepts valid URL, rejects
  malformed URL).
- `src/aeat/status/_parsers/test_expedientes.py` — two tests for
  detail-anchor capture (populated + absent).
- `tests/test_config.py` — new
  `TestStatusDetailUrlTemplate` class with three tests (populated
  default, default contains placeholder, invalid template
  rejected).
- `src/aeat/status/test_reader.py` — added:
  - `_UrlKeyedFakePage` — URL-keyed fake page preserving the
    `_FakePage` contract (same `visited: list[str]` semantics).
  - `_UrlKeyedBrowserSession` — session variant that vends the URL-
    keyed page.
  - `_build_url_keyed_reader(...)` — builder helper matching the
    existing `_build_reader` conventions.
  - `TestListExpedientes` — five tests covering no-filter,
    modelo-only, period-only, both-filters, single-underlying-fetch.
  - `TestStructuralProtocolConformance` — two isinstance checks
    against `ExpedienteSource` and `FilingDetailFetcher`.
  - `TestFetchDetailHtml` — six tests: detail_url verbatim, templated
    fallback, Settings override, HTTP ≥ 400, empty body, URL-safe
    quoting.
  - `TestFetchFilingDetail` — five tests: happy path, empty-when-no-
    match, unsupported-modelo, cache hit skips navigation, use_cache
    false forces re-fetch.
- `src/aeat/status/test_no_write_surface.py` — new safety guardrail
  mirroring `aeat/history/test_no_write_surface.py` (with
  self-exclusion preserved).

## verification

- `uv run pytest src/aeat/status/ src/aeat/history/ tests/test_config.py -q`
  → **193 passed**, 2 deselected.
- `uv run pytest -m unit -q` → **1732 passed**, 1 skipped, 27 deselected.
- `uv run ruff check src/aeat tests/` → clean.
- `uv run ruff format --check src/aeat tests/` → 590 files already
  formatted.

## notes

No new test fixtures were needed beyond the additive
`sample_with_detail.html` and the existing filing-history
fixtures (`modelo_303_detail.html`). No mocks, patches, or fakes
were used — every test double is a real Protocol-conforming class.
