---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S117'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S117

Added a settings-centralisation guard for inbound declaration/PDF production
modules.

- Modified: `src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py`

## Description

Extended the inbound hygiene test module with an AST check that rejects direct
`os.environ`, `os.getenv`, and imported `getenv` access in declaration/PDF
production modules. This keeps parser code routed through existing core
settings and access-gate surfaces instead of local environment wrangling.

## Tests

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py -q`
