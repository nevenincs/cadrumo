---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
---

# `aeat-restructure` audit-3 `access-gate-move`

Relocate `AeatAccessGate`, `AeatGateEnvSnapshot`, `AeatLiveReadNotEnabledError`,
`LiveSubmitForbiddenError`, `SubmissionError`, and `SubmissionPreflightError`
into `src/aeat/core/access_gate/`. No shims — all importers updated directly.

- Created: `src/aeat/core/access_gate/__init__.py`
- Created: `src/aeat/core/access_gate/_errors.py`

## Description

The `core-is-leaf` import-linter contract forbids `aeat.core` from importing
`aeat.adapters`. Moving `AeatAccessGate` to core therefore requires co-relocating
`AeatLiveReadNotEnabledError` (previously in `certificate.py`) and the full
`LiveSubmitForbiddenError` hierarchy (`SubmissionError`, `SubmissionPreflightError`,
`LiveSubmitForbiddenError` — previously in `adapters/outbound/aeat/export/_errors.py`).

`_registry.py` qualname keys updated from the old adapter paths to the new core paths.
`adapters/outbound/aeat/auth/_gate.py` deleted; its content now lives in core.
All importers updated without shims.

## Tests

```
uv run pytest src/aeat/core/ src/aeat/adapters/outbound/aeat/auth/ src/aeat/adapters/outbound/aeat/export/ -x -q
uv run ruff check src/aeat/core/access_gate/ src/aeat/adapters/outbound/aeat/auth/ src/aeat/adapters/outbound/aeat/export/
uv run pyright src/aeat/core/access_gate/ --outputjson 2>&1 | tail -3
```
