---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S19'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S19 - config diagnostics verification

Scope: `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/entrypoints/cli/_config/_auth_diagnostics.py`, and `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

## Description

- Ran Ruff over the touched config CLI files and size guard.
- Ran Python compileall over the touched config package and size guard.
- Ran direct CLI help checks for `config auth diagnostics list/show/report`.
- Ran output-language parity tests with the repository marker filter disabled so the diagnostics cases executed.
- Ran the config/app help-shape test with the marker filter disabled.
- Ran the CLI module and command size guard.
- Ratcheted `_config/__init__.py` from 2890 to 2705 lines.

## Outcome

Verification passed for the touched behavior:

```text
uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_auth_diagnostics.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py
All checks passed.

uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_config src/aeat/entrypoints/cli/tests/test_cli_module_size.py
passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_output_language_parity.py -m "" -q
40 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_root_help_shape.py::test_config_and_app_help_use_curated_subtree_shape -m "" -q
1 passed

uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q
2 passed

ad hoc invoke_cached_cli help checks for config auth diagnostics list/show/report
all exit_code 0 and --output-language present
```

The guard count uses Python `splitlines()`: `_config/__init__.py` is now 2705 lines and `_config/_auth_diagnostics.py` is 201 lines.

## Notes

Running the full `test_root_help_shape.py` module with `-m ""` exposed an unrelated failing profile-create wording assertion: the live output now contains `DNI/NIE/NIF/CIF` while the test expected `NIF`. The touched config/app help-shape test passed separately.
