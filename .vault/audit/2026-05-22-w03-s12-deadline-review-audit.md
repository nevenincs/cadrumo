---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-taxpayer-type-applicability-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-research]]'
---

# `w03-s12-deadline` Code Review

W03S12-001 | HIGH | Modelo 202 registered windows are filtered out of the deadline engine
 The new Modelo 202 filing schedule declares `periods = ["1P", "2P", "3P"]`, but the registered deadline windows declare period values such as `2025-1P` and `2026-1P`. The deadline engine only normalizes quarterly window periods containing `Q` or ending in `T`; `2026-1P` is passed through unchanged and does not match the schedule periods. In addition, the schedule declares no `profile_conditions`, and the schedule selector treats an empty condition result as false. A real `DeadlineEngine().compute(..., 2026)` run returns no Modelo 202 obligations. Evidence: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/filing_schedules/0001-modelo-202-2025-y-siguientes-trimestral.toml`; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0001-modelo-202-2025-1p.toml`; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0004-modelo-202-2026-1p.toml`; `src/aeat/domain/calculations/registry/test_modelo_202_registry.py`.

W03S12-002 | MEDIUM | Modelo 202 deadline test does not exercise consumer applicability
 The committed test validates raw registry references, hard-coded dates, and snapshot construction by explicit period, but it never asks the deadline consumer to compute a schedule for a legal-entity taxpayer and assert that Modelo 202 appears for 1P, 2P, and 3P. That leaves the period/schedule mismatch and empty-condition selector behaviour uncovered even though the slice adds a `deadline` application link for `aeat.domain.deadlines`. Evidence: `src/aeat/domain/calculations/registry/test_modelo_202_registry.py`; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/application_links/0010-modelo-202-deadline.toml`.

W03S12-003 | RESOLVED | Modelo 202 deadline consumer path now resolves
 Follow-up fixed the Modelo 202 schedule by using the declared `taxpayer.entity_type` user-profile selector, adding a legal-entity predicate, normalising quarterly `P` instalment windows such as `2026-1P` to schedule period `1P`, and adding real deadline-engine tests for legal-entity and natural-person profiles. Reviewer follow-up found no new issues and confirmed W03.S12 is safe to close. Evidence: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/filing_schedules/0001-modelo-202-2025-y-siguientes-trimestral.toml`; `src/aeat/domain/deadlines/_engine.py`; `src/aeat/domain/calculations/registry/_schedules.py`; `src/aeat/domain/deadlines/test_engine.py`.
