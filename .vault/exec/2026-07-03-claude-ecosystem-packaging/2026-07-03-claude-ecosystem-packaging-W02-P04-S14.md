---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S14'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Test the seam resolves a corpus binary identically whether it lives under the aeat tree or the aeat_data companion root

## Scope

- `src/aeat/core/resources/tests/test_corpus_companion_seam.py`

## Description

- Add `test_corpus_companion_seam.py` proving a corpus binary resolves identically whether it lives under the `aeat` tree or under an `aeat_data` companion root (real temp package on `sys.path` carrying a mirrored file — no mocks).
- Commit `c17aca069f`.

## Outcome

- The seam contract is locked by real-behaviour tests on both resolution paths.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before it could report. Gate re-verified post-hoc at the coordinator: `pytest src/aeat/core/resources/tests/test_corpus_companion_seam.py` green.
