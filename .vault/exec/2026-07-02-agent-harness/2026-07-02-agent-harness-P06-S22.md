---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# harden category 3 response provenance so expected computed response rows require formula_id

## Scope

- `src/aeat/agent/eval/_runner.py`
- `src/aeat/agent/eval/tests/test_response_provenance_golden.py`

## Description

- Ground the response-layer gap with `uvx vaultspec-rag search "agent golden eval calculate response payload formula_id computed casilla provenance" --type code --limit 8`.
- Confirmed the category-3 golden eval already dispatched a real `modelo.work.calculate` response, but `_check_response_provenance` only enforced `legal_refs` and `source_refs`.
- Tightened `_check_response_provenance` so every response observation still needs legal/source refs and every scenario-declared expected computed casilla must appear in the response with non-empty `formula_id`.
- Extended the real M130 response test to assert expected computed response rows carry `formula_id`.
- Added an anti-tautology proof that strips only `formula_id` from expected computed rows and verifies the response-provenance dimension fails.
- Added a negative-control proof that clears `formula_id` only on response rows outside the expected computed-casilla contract and verifies the response-provenance dimension still passes.

## Outcome

- `uv run --no-sync pytest -q -n 0 -m integration src\aeat\agent\eval\tests\test_response_provenance_golden.py`: 5 passed.
- `uv run --no-sync pytest -q -n 0 -m integration src\aeat\agent\eval\tests\test_modelo_130_golden.py`: 14 passed.
- `uv run --no-sync pytest -q -n 0 -m integration src\aeat\agent\eval\tests\test_response_provenance_golden.py src\aeat\agent\eval\tests\test_modelo_130_golden.py`: 19 passed.
- `uv run --no-sync ruff check src\aeat\agent\eval\_runner.py src\aeat\agent\eval\tests\test_response_provenance_golden.py`: passed.
- Independent `vaultspec-code-reviewer` review found no blocking findings; the only residual it named was closed by the negative-control test in this step.

## Notes

- The repository's default pytest marker selection deselects these integration tests without `-m integration`; the focused default-marker probe reported 14 deselected for `test_modelo_130_golden.py`.
- Feature-scoped vault checks for placeholders, body links, and frontmatter passed. `annotations` still reports pre-existing scaffold comments in `P07.S20` and `P07.S21`; `modified-stamp` still reports the pre-existing ADR stamp drift on `2026-07-02-agent-harness-refoundation-adr`.
