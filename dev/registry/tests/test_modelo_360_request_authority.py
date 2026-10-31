"""Modelo 360's request-specific eligibility and full-year filing window."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from cadrumo.application.modelo.profile_readiness_gate import modelo_applicability_refusal
from cadrumo.application.overview.calendar import build_overview_calendar
from cadrumo.application.overview.calendar_models import OverviewCalendarRange
from cadrumo.application.overview.coverage import CoverageAdviceReason
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.applicability import derive_modelo_applicability
from cadrumo.domain.calculations.registry.applicability_models import ApplicabilityVerdict
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.iva_regime_vocabulary import require_iva_regime
from cadrumo.domain.contribuyente.entity_type import require_entity_type
from cadrumo.domain.deadlines.models import ObligationStatus, TaxpayerProfile
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from dev.registry.compiler.authority import compiled_bundled_authority

if TYPE_CHECKING:
    from dev.registry.tests.committed_authority_publication import RunPublishedAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]


def _profile(entity: str, regime: str) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=require_entity_type(entity),
        iva_regime=require_iva_regime(regime),
    )


@pytest.mark.parametrize("entity", ("natural_person", "legal_entity", "attribution_entity"))
@pytest.mark.parametrize("regime", ("GENERAL", "EXENTO"))
def test_request_specific_eligibility_is_undetermined(entity: str, regime: str) -> None:
    authority = compiled_bundled_authority()
    result = derive_modelo_applicability(_profile(entity, regime), "360", today=date(2026, 4, 1), authority=authority)
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "otros Estados miembros" in result.reason
    assert "Canarias, Ceuta o Melilla" in result.reason
    assert "períodos más cortos" in result.reason


def test_missing_entity_is_incomplete_and_303_still_applies_to_general_company() -> None:
    authority = compiled_bundled_authority()
    missing = TaxpayerProfile(tax_id="B12345674", iva_regime=require_iva_regime("GENERAL"))
    assert derive_modelo_applicability(missing, "360", today=date(2026, 4, 1), authority=authority).verdict is (
        ApplicabilityVerdict.INCOMPLETE
    )
    assert (
        derive_modelo_applicability(
            _profile("legal_entity", "GENERAL"), "303", today=date(2026, 4, 1), authority=authority
        ).verdict
        is ApplicabilityVerdict.APPLICABLE
    )


def test_full_year_2025_request_window_and_schedule() -> None:
    snapshot = compiled_bundled_authority().snapshot("360", filing_year=2025, period="0A")
    assert snapshot.modelo.cadence == "event"
    schedule = next(row for row in snapshot.revision.filing_schedules if row.id == "modelo-360-anual")
    assert schedule.period_kind == "event"
    assert schedule.periods == ("0A",)
    window = next(row for row in snapshot.revision.deadline_windows if row.id == "modelo-360-2025-anual")
    assert str(window.period) == "2025 0A"
    assert (window.period_kind, window.opens_on, window.closes_on) == (
        "event",
        date(2026, 1, 1),
        date(2026, 9, 30),
    )


def test_calendar_advises_and_local_work_does_not_refuse_unknown_request(
    committed_published_authority: RunPublishedAuthority,
) -> None:
    profile = _profile("legal_entity", "GENERAL")
    indexed = IndexedRegistryAuthority(committed_published_authority.descriptor_path)
    with indexed.operation() as operation:
        calendar = build_overview_calendar(
            profile,
            OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
            operation=operation,
            today=date(2026, 4, 1),
        )
        assert all(entry.modelo != "360" for entry in calendar.entries)
        advice = next(item for item in calendar.coverage.advised if item.modelo == "360")
        assert advice.reason is CoverageAdviceReason.APPLICABILITY_UNDETERMINED
        period = Period.from_year_and_code(2025, "0A")
        bucket_id = "36036036-0360-4360-8360-360360360360"
        revision_id = "2010-y-siguientes"
        created = datetime(2025, 1, 2, tzinfo=UTC)
        work_unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id=bucket_id,
                modelo=ModeloCode("360"),
                filing_year=2025,
                period=period,
                revision_id=revision_id,
            ),
            bucket_id=bucket_id,
            modelo=ModeloCode("360"),
            filing_year=2025,
            period=period,
            revision_id=revision_id,
            name="refund",
            created_at=created,
            updated_at=created,
        )
        overdue = build_overview_calendar(
            profile,
            OverviewCalendarRange(from_date=date(2026, 9, 1), to_date=date(2026, 10, 31)),
            operation=operation,
            today=date(2026, 10, 15),
            work_units=(work_unit,),
        )
        entry = next(item for item in overdue.entries if item.local_work_unit_id == work_unit.work_unit_id)
        assert entry.status is ObligationStatus.OVERDUE
        assert entry.recovery is None
        assert entry.recovery_action is None
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id="36036036-0360-4360-8360-360360360360",
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.tax_id", value="B12345674"),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            ),
        )
        assert modelo_applicability_refusal(record=record, bucket_id="test", modelo="360", operation=operation) is None
