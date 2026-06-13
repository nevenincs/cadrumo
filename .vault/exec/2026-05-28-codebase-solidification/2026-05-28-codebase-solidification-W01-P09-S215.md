---
step_id: S215
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S215 — module-level test coverage inventory enumeration

## Outcome

Enumeration pass complete. Walked every production Python module under `src/aeat/`
(381 modules, excluding `__init__.py`, `conftest.py`, `fixtures.py`, `__pycache__`).
Identified 71 modules in directories with no paired `test_*.py` file.

Wave 2 follow-up targets (registered in `COVERAGE_GAPS` in `test_coverage_inventory.py`):
- 4 adapter/inbound sub-parser backends (borrador, declaracion, justificante)
- 3 certificate backend helpers (httpx, playwright, base)
- 6 LLM provider implementations (anthropic, gemini, openai, local, base, deterministic)
- 5 core error registry sub-packages + access gate errors
- 1 reconciliation errors module
- 49 portal entry definitions (domain/portals/_entries/)
- 2 test-fixture generator scripts

## Files touched

None (enumeration pass; results registered in S216 test file).

## Verification

See S216 test file.
