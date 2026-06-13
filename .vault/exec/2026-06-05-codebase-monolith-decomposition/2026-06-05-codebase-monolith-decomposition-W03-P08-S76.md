---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S76'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S76 AEAT Auth Adapter Verification

Scope: verify AEAT auth adapter behavior and facade imports after decomposition.

## Description

- Run `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/auth src/aeat/entrypoints/cli/_config/tests`.
- Run `uv run --no-sync pytest src/aeat/adapters/outbound/aeat/auth/tests -q --tb=short`.
- Run `uv run --no-sync pytest src/aeat/entrypoints/cli/_config/tests -q --tb=short -m integration`.
- Run an import smoke for `AeatAuthenticator`, `ClaveMovilAuthProvider`, and `AeatSession` from the top-level auth facade.
- Search application, entrypoint, domain, and adapter code for direct imports into the new private auth decomposition modules.

## Outcome

Auth adapter tests passed with 152 selected tests and 6 deselected tests. Config entrypoint integration tests passed with 40 tests. Ruff passed for the touched auth and config-test surface. The top-level auth facade import smoke succeeded. The private-module consumer search returned no matches outside same-package auth internals and tests.

## Notes

Running the config test directory without a marker override collected 40 tests but selected none because project defaults select `unit` while those tests are marked `integration`. The verification lane was rerun with `-m integration` and passed.
