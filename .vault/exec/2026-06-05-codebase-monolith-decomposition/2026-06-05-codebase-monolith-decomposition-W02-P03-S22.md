---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S22'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S22 - residual config apoderado verification

Scope: `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/entrypoints/cli/_config/_apoderado.py`, and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched config CLI files and size guard.
- Ran Python compileall over the touched config files and size guard.
- Ran apoderado integration tests for no-profile refusal and scopes listing.
- Ran direct CLI help checks for all apoderado commands through the root CLI surface.
- Ran output-language parity tests with the repository marker filter disabled.
- Ran the CLI module and command size guard.
- Ratcheted `_config/__init__.py` from 2705 to 2500 lines.

## Outcome

Verification passed for the touched behavior:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_apoderado.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_apoderado.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
passed

uv run --no-sync pytest src/aeat/entrypoints/cli/_config/tests/test_apoderado.py::test_apoderado_status_fails_without_profile src/aeat/entrypoints/cli/_config/tests/test_apoderado.py::test_apoderado_scopes_list -m integration -q
2 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_output_language_parity.py -m "" -q
40 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for config auth apoderado scopes/status/configure/clear/check
all exit_code 0 and --output-language present
```

The guard count uses Python `splitlines()`: `_config/__init__.py` is now 2500 lines and `_config/_apoderado.py` is 238 lines.

## Notes

The full `test_apoderado.py` module still has one unrelated failure in `test_apoderado_happy_path_against_active_profile`: it imports the config sub-app but invokes it with a leading `config` command noun, producing `No such command 'config'`. The two apoderado tests that exercise the extracted subtree pass, and root CLI help checks confirm the public command path is mounted.
