---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S115'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S115

Extended exception-swallowing hygiene tests to inbound declaration/PDF
production modules.

- Created: `src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py`

## Description

Added AST guard tests for the inbound declaration and shared inbound PDF
production modules. The tests reject:

- pass-only exception handlers,
- bare `except`,
- `contextlib.suppress`, and
- broad `Exception`/`BaseException` handlers that neither re-raise nor log.

This mirrors the existing registry exception hygiene guard and makes the
pypdfium2 fallback policy explicit: fallback is acceptable only because it
logs at debug level before returning `None`.

## Tests

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py src\aeat\domain\calculations\registry\test_exception_hygiene.py -q`
