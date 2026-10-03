---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-10-03'
body_hash: 'sha256:6a1a65602590fac7d8a5da30176a5198d6a2af6b96fdbdcc8309f3bfb98e4123'
related: []
---

# `calculation-truth-registry` `adjacent-modelo` `registry-closure`

Closed adjacent registry validation gaps exposed while driving the Modelo 100
Renta dependency slice.

- Modified: `registry/aeat/modelos/202.toml`
- Modified: `registry/aeat/modelos/232.toml`
- Modified: `registry/aeat/modelos/349.toml`

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
