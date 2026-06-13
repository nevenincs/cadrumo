---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S114'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S114

Added explicit exception hierarchy guards for declaration, PDF, and registry
error surfaces.

- Modified: `src/aeat/adapters/inbound/declaracion/__init__.py`
- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- Modified: `src/aeat/domain/calculations/registry/test_exception_hygiene.py`

## Description

Exported `TemplateNotDetectedError` from the declaration parsing boundary and
added tests proving:

- `DeclaracionParseError` descends from the shared PDF import error and
  `AeatError`.
- `TemplateNotDetectedError` descends from `DeclaracionParseError`.
- Registry load, snapshot, and validation errors descend from `RegistryError`,
  which itself descends from `AeatError` and `ValueError`.

The existing inbound PDF shared tests already cover `PdfModeloImportError`
inheritance from `AeatError`; this step runs that test module as part of the
verification set.

## Tests

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\__init__.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\domain\calculations\registry\test_exception_hygiene.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\adapters\inbound\pdf\test_shared.py src\aeat\domain\calculations\registry\test_exception_hygiene.py -q`
