---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-07-17'
body_hash: 'sha256:b9dfb7336d2a0d90f07dd8ce5a72c397ca806a9748aa740c7f388b0a53b0e5ad'
step_id: 'S127'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W05.P16.S127`

Fixed the Modelo 303 submitted-file export-layout regression discovered during
broader Sede validation.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`

## Description

Modelo 303 now has a registry export layout, so page-03-only submitted-file
fixtures were no longer reaching the existing Modelo 303 page-03 parser. The
full export parser attempted to parse those fragments as envelope-starting
payloads and failed at `modelo-303-envelope-marker`.

The declarations adapter now falls back to the existing Modelo 303 page-03
parser only when the full export-layout parse fails and the submitted-file body
starts with the page-03 record tag. Full Modelo 303 payloads still use the
registry export layout. The fallback logs the failed full-layout parse at debug
level before using the page-03 parser, preserving observability.

## Tests

Passed:

- `uv run --no-sync pytest -q src\aeat\adapters\outbound\aeat\sede\test_declarations.py::test_modelo_303_submitted_file_fallback_extracts_result_casillas src\aeat\adapters\outbound\aeat\sede\test_declarations.py::test_modelo_303_2022_submitted_file_fallback_uses_2022_result_position src\aeat\adapters\outbound\aeat\sede\test_declarations.py::test_modelo_303_submitted_file_fallback_refuses_invalid_page_record_footer`
- `uv run --no-sync pytest -q src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\domain\calculations\registry\test_committed_registry.py`
- `uv run --no-sync ruff check src\aeat\adapters\outbound\aeat\sede\_declarations.py`
