---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-cli-workflow-redesign-W02-S08]]'
---



# `cli-workflow-redesign` Code Review

Status: PASS. No findings.

Scope reviewed: W02.S08 derivation changes in `src/aeat/application/overview/__init__.py` and `src/aeat/application/overview/test_calendar.py`, grounded against the taxpayer-type applicability plan, the W02.S08 execution record, the audit template, the W03.S11 applicability closure, the W03.S13 rate-schedule closure, and `src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py`.

The overview calendar now exposes `tax_route`, `calculation_selections`, and `rate_schedule_resolutions` from the declared taxpayer model. The filing entries still pass through the deadline engine but are filtered by positive registry-backed applicability verdicts, so non-applicable, pass-through, and incomplete model outcomes are not surfaced as confident due rows. Undeclared profiles return an explicit incomplete calendar with empty derivation payloads, preserving the no-guessing contract.

Calculation selection is derived from registry-owned applicability rules and the modelo resource catalogue. It includes only positively applicable modelos with non-informative calculation classes, and the tests exercise natural-person, legal-entity, attribution-entity, and undeclared routes without mocks, monkeypatching, skips, or xfails.

Rate and bracket schedule references are resolved through the central modelo registry authority: natural-person routes read Modelo 100 IRPF bracket parameters and CCAA dispatch references; legal-entity routes read the Modelo 200 LIS rate dispatch selected by `legal_entity_form`; attribution and undeclared routes yield no cuota schedule. Missing yearly registry snapshots degrade to an empty tuple rather than inventing a schedule.

No registry/deadline circular import was found. Runtime registry imports are kept inside derivation helpers, type-only registry imports remain guarded by `TYPE_CHECKING`, and the public applicability surface used by overview imports taxpayer model types through the non-cyclic deadline taxpayer-model module rather than through registry package initialization.

Residual risks: `rate_schedule_resolutions` is a calendar-level tuple for a single filing year selected from `OverviewCalendarRange.to_date.year`, not a per-entry or per-covered-year structure. This matches the W02.S08 execution description's singular filing-year behavior, but a future multi-year UX may need explicit per-year schedule resolution to avoid ambiguity. The seed applicability table remains intentionally narrow; unruled modelos continue to produce incomplete applicability rather than guessed obligations.

Verification performed during this audit:

- `uv run ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py` -> passed, all checks passed.
- `uv run pytest src/aeat/application/overview/test_calendar.py -q` -> passed with 49 tests.
- `uv run python -c "import aeat.application.overview as overview; import aeat.domain.deadlines as deadlines; import aeat.domain.calculations.registry.applicability as applicability; print(overview.TaxRoute.IRPF.value); print(deadlines.TaxpayerProfile.__name__); print(applicability.derive_tax_route(deadlines.TaxpayerProfile(entity_type=deadlines.EntityType.LEGAL_ENTITY)).value)"` -> failed because the smoke-test profile omitted required `tax_id` and `iva_regime` fields; this was a command construction error, not an import-cycle failure.
- `uv run python -c "import aeat.application.overview as overview; import aeat.domain.deadlines as deadlines; import aeat.domain.calculations.registry.applicability as applicability; profile = deadlines.TaxpayerProfile(tax_id='B12345674', entity_type=deadlines.EntityType.LEGAL_ENTITY, iva_regime=deadlines.IVARegime.GENERAL); print(overview.TaxRoute.IRPF.value); print(deadlines.TaxpayerProfile.__name__); print(applicability.derive_tax_route(profile).value)"` -> passed; output was `irpf`, `TaxpayerProfile`, `impuesto_sociedades`.
- `uv run pytest src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py -q` -> passed with 2 tests.
- `uv run aeat app registry verify` -> passed with `Verificado=True`.
- `uv run pytest src/aeat/application/overview/test_calendar.py src/aeat/application/overview/test_applicability.py src/aeat/application/overview/test_explain.py src/aeat/application/overview/test_agenda.py src/aeat/application/overview/test_backlog.py src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py src/aeat/domain/calculations/registry/test_modelo_applicability.py src/aeat/domain/deadlines/test_engine.py -q` -> passed with 169 tests.

## Follow-up Review - 2026-05-22

Status: PASS. The residual multi-year rate-schedule ambiguity is resolved.

Follow-up scope reviewed: `OverviewRateScheduleResolution` now carries `filing_year`, and `_rate_schedule_resolutions` receives `OverviewCalendarRange.covered_years()` from `build_overview_calendar`. The resolver iterates each covered year for both IRPF Modelo 100 and Impuesto sobre Sociedades Modelo 200 snapshots, so a multi-year calendar no longer collapses schedule references to only `to_date.year`. Each emitted schedule row is year-qualified; years with no registered snapshot still contribute no invented schedule row.

No new finding remains.

Verification performed during this follow-up:

- `uv run ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py` -> passed, all checks passed.
- `uv run pytest src/aeat/application/overview/test_calendar.py -q -k "covered_years or rate_schedule or derivation_selects_irpf or derivation_selects_is or derivation_resolves_rate_schedules"` -> passed with 4 selected tests and 46 deselected.
- `uv run python -c "from datetime import date; from aeat.application.overview import OverviewCalendarRange, build_overview_calendar; from aeat.domain.deadlines import EntityType, IVARegime, TaxpayerProfile; from aeat.domain.deadlines._models import LegalEntityForm; profile = TaxpayerProfile(tax_id='B12345674', entity_type=EntityType.LEGAL_ENTITY, legal_entity_form=LegalEntityForm.SL, iva_regime=IVARegime.GENERAL); rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2026, 12, 31)); cal = build_overview_calendar(profile, rng, today=date(2025, 7, 1)); print(sorted((r.filing_year, r.modelo, r.parameter_id, r.selector_value) for r in cal.rate_schedule_resolutions))"` -> passed; output was `[(2025, '200', 'is.modelo-200.tipo-gravamen-general', 'sl'), (2026, '200', 'is.modelo-200.tipo-gravamen-general', 'sl')]`.
