---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-wave1-step2-exec]]'
---



# `calculation-truth-registry-wave1-step2-cleanup` Code Review

CTR-W1S2C-001 | MEDIUM | Recovery-command placeholders still render as copy-paste commands

`src/aeat/core/errors/registry/_application.py` now uses `aeat app declaration calculate --modelo {modelo} --period {period}` for aggregation period and unsupported-modelo errors. This avoids Modelo 130 as a default, and it passes type checks, but `get_error_suggestion` renders suggestions as `Run `<suggestion>`` without interpolation. Users will see a command with literal braces, which is not copy-pasteable and is still a UX regression for an error recovery hint. Either make these suggestions concrete at throw-site via the exception `suggestion` override, or use a clearly documented non-command hint format instead of a `Run` command.

CTR-W1S2C-002 | LOW | Remaining numeric Modelo 130 examples are outside the actual portal entry

`src/aeat/adapters/outbound/aeat/sede/_declarations.py` still documents generic Sede declaration rows and queries with examples including `"130"` alongside `"100"` and `"303"`. This is not a filing authority and not a default selection, but it is also not the actual Modelo 130 portal entry. The exec record's final search only checks `Modelo 130`, `modelo_130`, `MODELO_130`, and old uppercase placeholders, so it does not catch these quoted numeric examples. If the intended standard is "only true Modelo 130 portal surfaces," these examples should be neutralized or the exec record should explicitly classify the generic read-only declarations reader as an allowed surface.

## Checks

- `uv run ruff check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py` passed.
- `uv run ty check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py` passed.
- Scoped search found no `MODELO_130`, `modelo_130`, `modelo-130`, `--modelo 130`, `--modelo MODELO`, or `--period PERIOD` in the five scoped Python files.
- Scoped search found remaining quoted numeric `"130"` examples only in the generic Sede declarations reader docstrings within the requested Python scope.
- `src/aeat/domain/justificante/__init__.py` no longer carries the Modelo 130 public API example.
- I did not re-review broad dirty worktree changes.

## Remediation Recheck

CTR-W1S2C-001 | OPEN | Recovery suggestion still renders as a fake command

`src/aeat/core/errors/registry/_application.py` no longer uses `{modelo}` or `{period}` placeholders, but the replacement value is prose: `Run declaration calculation with an explicit modelo and period.` The core formatter still renders every non-null suggestion as `Run `<suggestion>``. That means these errors will display `Run `Run declaration calculation with an explicit modelo and period.`` instead of either a real command or a documented non-command hint. The fake copy-paste command concern remains open.

CTR-W1S2C-002 | RESOLVED | Generic Sede declarations reader no longer carries numeric Modelo 130 examples

The generic examples in `src/aeat/adapters/outbound/aeat/sede/_declarations.py` were neutralized. The explicit non-test model-number scan now reports only actual portal entry modules for the checked model codes, including the Modelo 130 portal entry.

## Recheck Commands

- `uv run ruff check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py src\aeat\domain\_identifiers.py` passed.
- `uv run ty check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py src\aeat\domain\_identifiers.py` passed.
- `rg -n -g '*.py' -g '!**/test_*.py' -g '!*test*.py' -- 'MODELO_130|Modelo 130|modelo_130|MODELO_111|Modelo 111|modelo_111|MODELO_115|Modelo 115|modelo_115|MODELO_303|Modelo 303|modelo_303|--modelo MODELO|--period PERIOD|"130"|"111"|"115"|"303"' src\aeat\application src\aeat\domain src\aeat\adapters src\aeat\entrypoints` reports only actual portal entry modules.
- Scoped search found no `{modelo}`, `{period}`, `--modelo MODELO`, `--period PERIOD`, `MODELO_130`, `modelo_130`, or `modelo-130` in the scoped Python files.
- I did not re-review broad dirty worktree changes.

## Final Recheck

CTR-W1S2C-001 | RESOLVED | Aggregation defaults no longer emit fake copy-paste commands

The two application aggregation error codes now set `default_suggestion=None`, so `format_error_for_cli` will not render a misleading `Run` command for those cases. The registry contract test that requires remaining suggestions to parse as live Click commands passes.

CTR-W1S2C-002 | RESOLVED | Model-number examples remain limited to actual portal entry modules

No change from the prior recheck: the scoped model-number issue remains resolved.

## Final Checks

- `uv run pytest src\aeat\entrypoints\cli\test_error_registry_contract.py -q` passed: 8 tests.
- Scoped inspection confirmed `ERROR_FINANCIAL_AGGREGATION_PERIOD` and `REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO` both have `default_suggestion=None`.
- I did not re-review broad dirty worktree changes.
