---
tags:
  - "#exec"
  - "#aeat-filing-detail-fetch"
date: 2026-04-18
modified: '2026-04-18'
title: exec — phase 1 summary — schema and config
issue: wgergely/aeat#227
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-plan]]"
  - "[[2026-04-18-aeat-filing-detail-fetch-adr]]"
---

# exec — phase 1 summary — schema and config

## scope executed

Plan phases 1.1–1.5 (schema and config additions).

## artefacts

- `src/aeat/status/_models.py` — added
  `Expediente.detail_url: AnyHttpUrl | None = None`. Strict+frozen
  config preserved.
- `src/aeat/status/_parsers/expedientes.py` — added
  `_DETAIL_COLUMN_CANDIDATES` + `_extract_detail_anchor`. Parser
  captures the first matching `<a href>` under a ``Detalle`` /
  ``Acciones`` / ``Accion`` column. Backwards-compatible.
- `src/aeat/status/_parsers/test_expedientes.py` — two new tests
  (populated + absent detail column).
- `tests/fixtures/aeat-pages/expedientes/sample_with_detail.html` —
  new fixture with a ``Detalle`` column (one row populated, one
  blank). The original `sample.html` and `sample_spanish.html` are
  untouched so existing `test_reader.py:115 assert len(records) == 3`
  regressions remain green.
- `src/aeat/config.py` — added
  `aeat_status_detail_url_template: str` field (default
  `"/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"`) plus a
  `@field_validator` that rejects templates missing the
  `{expediente_id}` placeholder. Explicitly NOT added to the
  `_normalize_repo_relative_paths` validator list.
- `env/.env.example` — documented the new
  `AEAT_STATUS_DETAIL_URL_TEMPLATE` env var under the Status
  reader block.

## verification

- `uv run pytest src/aeat/status/_parsers/ src/aeat/status/test_models.py tests/test_config.py -q`
  → green (post phase 3).

## notes

No risk items surfaced. The `Expediente.detail_url` schema addition
is fully backwards-compatible — existing fixture parsers yield
`None` by default.
