---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S12'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
  - '[[2026-05-22-w03-s12-deadline-review-audit]]'
---

# `cli-workflow-redesign` `W03.S12`

Registered the remaining corporate Modelo 202 deadline windows for the 2025-y-siguientes revision and wired them into the deadline consumer path.

- Modified: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/constructs/0001-modelo-202-foundation.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/filing_schedules/0001-modelo-202-2025-y-siguientes-trimestral.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0001-modelo-202-2025-1p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0002-modelo-202-2025-2p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0003-modelo-202-2025-3p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0004-modelo-202-2026-1p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0005-modelo-202-2026-2p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0006-modelo-202-2026-3p.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/application_links/0010-modelo-202-deadline.toml`
- Modified: `src/aeat/domain/calculations/registry/_schedules.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_202_registry.py`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Modified: `src/aeat/domain/deadlines/test_engine.py`

## Description

The Modelo 202 registry now declares the three annual instalment periods for 2025 and 2026: `1P`, `2P`, and `3P`, with windows grounded in `ley-27-2014:art-40` and the committed `aeat-modelo-202-instructions` corpus source. The construct now links those filing schedules, deadline windows, and the `deadline` application surface.

The first review found that valid registry data was still not consumable by `DeadlineEngine`: window periods such as `2026-1P` did not normalise to schedule period `1P`, and the schedule did not carry a legal-entity predicate. The fix normalises quarterly `P` periods, resolves the declared `taxpayer.*` profile selector namespace against `TaxpayerProfile`, and requires `taxpayer.entity_type == legal_entity` for Modelo 202 schedule selection.

## Tests

Focused and broad gates passed:

- `uv run pytest src/aeat/domain/deadlines/test_engine.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/domain/calculations/registry/test_schedules.py -q` -> 58 passed.
- `uv run aeat app registry verify` -> `Verificado=True`.
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_347_registry.py src/aeat/domain/deadlines/test_engine.py src/aeat/application/overview/test_calendar.py src/aeat/application/overview/test_applicability.py -q` -> 182 passed.
- `uv run ruff check src/aeat/domain/calculations/registry/_schedules.py src/aeat/domain/deadlines/_engine.py src/aeat/domain/deadlines/test_engine.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py` -> passed.

The code review record is `2026-05-22-w03-s12-deadline-review`.
