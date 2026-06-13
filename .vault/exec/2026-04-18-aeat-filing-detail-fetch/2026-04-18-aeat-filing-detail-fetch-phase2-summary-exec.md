---
tags:
  - "#exec"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: exec — phase 2 summary — reader surface
issue: wgergely/aeat#227
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-plan]]"
  - "[[2026-04-18-aeat-filing-detail-fetch-adr]]"
---

# exec — phase 2 summary — reader surface

## scope executed

Plan phases 2.1–2.5.

## artefacts

- `src/aeat/status/_reader.py` — new public methods on
  :class:`StatusReader`:
  - `list_expedientes(*, modelo=None, period=None, use_cache=True)`
    — post-parse filter over `fetch_expedientes`; structurally
    conforms to `aeat.history.ExpedienteSource` Protocol.
  - `fetch_detail_html(expediente)` — single-`page.goto` detail
    fetcher; structurally conforms to
    `aeat.history.FilingDetailFetcher` Protocol. Refuses
    HTTP ≥ 400 and empty bodies with `StatusReaderError` that
    carries the expediente_id + HTTP status.
  - `fetch_filing_detail(modelo, period, *, use_cache=True)` —
    composition facade that constructs a `HistoryFetcher`
    internally (via function-scoped import, per ADR D5) wrapping
    `self` as both collaborators and delegates to
    `fetch_for_modelo`.
- New private helper: `_build_detail_url(expediente)` — resolution
  order (ADR D6): expediente `detail_url` first, templated fallback
  second; `urllib.parse.quote` for URL-safe substitution.
- New module-level constant:
  `_EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT` — defensive fallback
  when Settings override is blank.
- New `TYPE_CHECKING` import: `from ..history import FiledModelo`
  for the return-type annotation only. Runtime history import
  stays function-scoped inside `fetch_filing_detail`.
- `src/aeat/status/__init__.py` — module docstring updated to
  describe the #227 surface and the two Protocol-conformance roles.

## verification

- `grep -rE "^from \.\.history|^import .*history" src/aeat/status/*.py src/aeat/status/_parsers/*.py`
  → only `test_reader.py` (test files allowed per ADR).
- ruff check + format clean.
- No `page.fill/click/submit` anywhere under `src/aeat/status/`.

## notes

The ADR D5 wording was tightened after execution to clarify that
the top-level history-import prohibition applies to production
modules; test modules may import at the top because pytest only
loads them after the package is fully initialised.
