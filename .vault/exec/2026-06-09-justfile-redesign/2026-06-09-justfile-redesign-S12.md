---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:eaf75370d2a09df3465e121839ee248a8aa1f386f963145f3761c2ae410f0dcf'
step_id: 'S12'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor modelo conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/application/modelo/tests/conftest.py`

## Description

- Refactored `modelo/tests/conftest.py` to eliminate wildcard import of `_file_flow_support`.
- Declared explicit import for the `repos` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and modelo application tests execute without error.

## Notes
