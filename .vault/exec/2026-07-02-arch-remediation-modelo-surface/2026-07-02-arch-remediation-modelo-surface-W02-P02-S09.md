---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:986fa45f87bf8d9d628d71c2c294b15fb8c51185838b0bd216b08b6839ab8525'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Confirm the existing grounded M100 calculation tests compute identical values before and after the parameter relocation, tolerating zero numeric drift

## Scope

- `src/aeat/domain/calculations/registry/tests`

## Description

- Update the grounded M100 Art. 85 calculation test to expect the registry-authored year-days parameter in formula provenance.
- Keep the external numeric oracle unchanged: the manual cadastral example still asserts `448.80`.
- Add neutral unrelated profile bindings required by the current Modelo 100 registry so the Art. 85 test reaches the formula under test.

## Outcome

- The grounded M100 Art. 85 test file passed: `5 passed`.
- Focused ruff check passed for the edited test file.
- No expected calculation values changed.

## Notes

- Pytest log: `_scratch-codex/w2_s09_m100_art85_pytest.log`.
- Ruff log: `_scratch-codex/w2_s09_ruff.log`.
