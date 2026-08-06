---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:df71dccc5614a1df731dffa381740daf9da6e58cae70ac0e6c784c7a86900fdc'
step_id: 'S369'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Retarget setup_answers._ccaa() to resolve CCAA from the public aeat.domain.contribuyente facade instead of the private aeat.domain.contribuyente._ccaa submodule

## Scope

- `src/aeat/core/setup_answers.py`

## Description

- Retargeted `_ccaa()`'s deferred `importlib.import_module` call from the private `aeat.domain.contribuyente._ccaa` submodule to the public `aeat.domain.contribuyente` package facade, keeping `.CCAA` attribute access and the same lazy-resolution cycle-break technique.
- Verified live: `aeat.domain.contribuyente` carries `CCAA` in its `__all__`, so the retarget resolves identically.

## Outcome

Committed alongside S364, S368, and S388 in one commit (`b6aafa707`). `src/aeat/core/tests -k setup_answers` and `src/aeat/domain/deadlines/tests` green; `pytest --collect-only -q src/aeat` clean.

## Notes

None.
