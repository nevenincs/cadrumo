---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `calculation-truth-registry` `adjacent-modelo` `registry-closure`

Closed adjacent registry validation gaps exposed while driving the Modelo 100
Renta dependency slice.

- Modified: `registry/aeat/modelos/202.toml`
- Modified: `registry/aeat/modelos/232.toml`
- Modified: `registry/aeat/modelos/349.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_202_registry.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`

## Description

Modelo 202 now declares a static official-documentation cross-reference,
portal application link, and foundation construct around its calculation,
filing, verification, workbook parity, and static evidence surfaces.

Modelo 232 now declares deadline application links for both supported
revisions and includes those links in its informative construct so deadline
windows pass the registry application-link closure gate.

Modelo 349 now declares an informative construct covering manual record-design
casillas, workbook parity, static documentation, and application links. Focused
tests now prove Modelo 202, 232, and 349 validate as committed registry
definitions and do not silently break the cross-dependency contract.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py`
  passed.
- `git diff --check` passed with a pre-existing CRLF warning in
  `src/aeat/locales/en.yml`.
