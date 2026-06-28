---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `modelo-130` `shared-surface-teardown`

Neutralized shared runtime examples and comments that used Modelo 130 as a
generic sample outside the registry, official corpus, or explicit Modelo 130
fixtures.

- Modified: `src/aeat/core/errors/registry/_application.py`
- Modified: `src/aeat/adapters/outbound/llm/__init__.py`
- Modified: `src/aeat/domain/manuals/_schema.py`
- Modified: `src/aeat/domain/manuals/_loader.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/records.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/_orm.py`
- Modified: `src/aeat/domain/justificante/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_parse.py`
- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/application/review/_filter.py`
- Modified: `src/aeat/domain/_identifiers.py`
- Modified: `src/aeat/domain/filing/reconciliation/__init__.py`
- Modified: generic application/domain schema docstrings that carried Modelo
  130 as their default sample.
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

This step does not mark Modelo 130 teardown complete. It removes one specific
source of drift: shared code surfaces that made Modelo 130 look like the
default calculation or filing example. The changes are documentation/default
suggestion cleanup only; no registry schema, calculation authority, portal
binding, parser behaviour, fixture value, or compatibility path was added.
Generic calculation error rows now omit a default suggestion when no
copy-paste-safe command exists; the renderer treats suggestions as commands.

The remaining runtime Modelo 130 references are expected surfaces: actual
portal identifiers/catalogue entries, registry TOML, official corpus, committed
Modelo 130 fixtures, and explicit Modelo 130 behaviour tests.

## Tests

- `uv run ruff check src\aeat\core\errors\registry\_application.py src\aeat\adapters\outbound\llm\__init__.py src\aeat\domain\manuals\_schema.py src\aeat\domain\manuals\_loader.py src\aeat\adapters\persistence\storage\sql\records.py src\aeat\adapters\persistence\storage\sql\_orm.py`
- `uv run ty check src\aeat\core\errors\registry\_application.py src\aeat\adapters\outbound\llm\__init__.py src\aeat\domain\manuals\_schema.py src\aeat\domain\manuals\_loader.py src\aeat\adapters\persistence\storage\sql\records.py src\aeat\adapters\persistence\storage\sql\_orm.py`
- `uv run ruff check src\aeat\application\workflow\_models.py src\aeat\application\filing\_history_repository.py src\aeat\application\filing\_export.py src\aeat\application\filing\_calculate.py src\aeat\application\verification\_schema.py src\aeat\application\overview\__init__.py src\aeat\domain\submission\_models.py src\aeat\domain\filing\_protocols.py src\aeat\domain\justificante\_schema.py src\aeat\adapters\inbound\declaracion\_schema.py src\aeat\adapters\inbound\justificante\_extract.py`
- `uv run ty check src\aeat\application\workflow\_models.py src\aeat\application\filing\_history_repository.py src\aeat\application\filing\_export.py src\aeat\application\filing\_calculate.py src\aeat\application\verification\_schema.py src\aeat\application\overview\__init__.py src\aeat\domain\submission\_models.py src\aeat\domain\filing\_protocols.py src\aeat\domain\justificante\_schema.py src\aeat\adapters\inbound\declaracion\_schema.py src\aeat\adapters\inbound\justificante\_extract.py`
- `uv run ruff check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py`
- `uv run ty check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py`
- `uv run ruff check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py`
- `uv run ty check src\aeat\core\errors\registry\_application.py src\aeat\domain\justificante\__init__.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\application\overview\__init__.py src\aeat\application\review\_filter.py`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_workbook_parity.py -q`
- `uv run ruff check src\aeat\adapters\outbound\aeat\sede\_parse.py src\aeat\domain\filing\reconciliation\__init__.py`
- `uv run ty check src\aeat\adapters\outbound\aeat\sede\_parse.py src\aeat\domain\filing\reconciliation\__init__.py`
- `uv run ruff check src\aeat\domain\_identifiers.py`
- `uv run ty check src\aeat\domain\_identifiers.py`
- `uv run pytest src\aeat\entrypoints\cli\test_error_registry_contract.py -q`
- `rg -n -g '*.py' -g '!**/test_*.py' -g '!*test*.py' -- 'MODELO_130|Modelo 130|modelo_130|MODELO_111|Modelo 111|modelo_111|MODELO_115|Modelo 115|modelo_115|MODELO_303|Modelo 303|modelo_303|--modelo MODELO|--period PERIOD|"130"|"111"|"115"|"303"' src\aeat\application src\aeat\domain src\aeat\adapters src\aeat\entrypoints` now reports only actual portal entry modules.
