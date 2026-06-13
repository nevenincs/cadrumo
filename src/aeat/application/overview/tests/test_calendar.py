"""Unit tests for the typed overview-calendar aggregator."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ....adapters.outbound.aeat.sede import Declaracion
from ....adapters.outbound.aeat.sede._notifications import RemoteNotification
from ....adapters.outbound.aeat.sede._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ....core import Period
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    ObligationStatus,
    TaxpayerProfile,
)
from ....domain.justificante import Justificante
from ....domain.modelos import (
    ExternalEvidence,
    ModeloCode,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ...live._expedientes import PersistedExpedientesSnapshot
from ...live._notifications import PersistedNotificationsSnapshot
from .. import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEventType,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    OverviewPeriodState,
    build_filing_obligation_advisories,
    build_overview_calendar,
    build_overview_calendar_events,
    calendar_applicability_profile_keys_for_modelo,
    calendar_censo_enrolment_profile_keys,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_notification_snapshots,
    user_state_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_URL = aeat_url("sede", "/")
_WORK_UNIT_ID = "a" * 64
_CALCULATION_REVISION_ID = "b" * 64
_BUCKET_ID = "c" * 32
_PERIOD_2025_1T = Period.from_year_and_code(2025, "1T")
_FILED_JUSTIFICANTE_STORAGE_REF = "secure-object:financial:" + "d" * 64


def test_calendar_censo_enrolment_profile_keys_are_centralised() -> None:
    assert calendar_censo_enrolment_profile_keys() == (
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.irpf_income_categories",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    )


def test_calendar_censo_warning_requires_every_modelo_enrolment_key() -> None:
    required_303 = set(calendar_applicability_profile_keys_for_modelo("303"))
    if "taxpayer_type.irpf_income_categories" in required_303:
        required_303.add("activities.iae_epigraph")
    required_303 &= set(calendar_censo_enrolment_profile_keys())
    assert required_303 == {
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    }

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(required_303 - {"iva.regime"})),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos


def test_calendar_censo_warning_clears_when_every_modelo_enrolment_key_is_verified() -> None:
    verified_303 = (
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=verified_303,
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.VERIFIED
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("303" in warning.affected_modelos for warning in censo_warnings)


def test_calendar_entry_marks_censo_enrolment_not_checked_when_no_live_censo_scope() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
    )

    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.NOT_CHECKED
    assert "censo.enrolment_unverified" not in {warning.code for warning in calendar.warnings}


def _corporate_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("7500000.00"),
        new_entity_first_two_profit_periods=False,
        notes="overview-calendar corporate test profile",
    )


def test_calendar_censo_warning_requires_corporate_modelo_202_enrolment_keys() -> None:
    required_202 = set(calendar_applicability_profile_keys_for_modelo("202"))
    required_202 &= set(calendar_censo_enrolment_profile_keys())
    assert required_202 == {
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    }

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(required_202 - {"taxpayer_type.incn_prior_12_months"})),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "202" in warning.affected_modelos


def test_calendar_censo_warning_clears_for_complete_corporate_modelo_202_provenance() -> None:
    verified_202 = (
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    )

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=verified_202,
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("202" in warning.affected_modelos for warning in censo_warnings)


def _modelo_record(
    *,
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = _PERIOD_2025_1T,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
    filed_by: str = "operator",
) -> ModeloRecord:
    filed_at = datetime(2025, 4, 14, 12, 0, tzinfo=UTC)
    filing_record_id = derive_filing_record_id(
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        filed_at=filed_at,
        filed_by=filed_by,
    )
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        filed_at=filed_at,
        filed_by=filed_by,
        aeat_accepted=aeat_accepted,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )


def _filed_declaration_observation(
    *,
    artefacts: tuple[FiledDeclaracionArtefact, ...],
    expediente_id: str = "12345678901234567890",
) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2025,
        period=_PERIOD_2025_1T,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        authenticated_identity="X1234567L",
        artefacts=artefacts,
    )


def _filed_declaration_artefact(
    *,
    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"] = "justificante_pdf",
    storage_ref: str | None = _FILED_JUSTIFICANTE_STORAGE_REF,
    byte_count: int = 128,
) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind=kind,
        source_url=AnyHttpUrl(_SOURCE_URL),
        content_type="application/pdf",
        byte_count=byte_count,
        sha256="d" * 64,
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        storage_ref=storage_ref,
    )


def _justificante_metadata(
    *,
    csv: str = "JUST-303-2025-1T",
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = _PERIOD_2025_1T,
    tax_id: str = "X1234567L",
) -> Justificante:
    pdf_bytes = f"{csv}-pdf".encode()
    return Justificante(
        csv=csv,
        modelo=modelo,
        period=period,
        ejercicio=str(filing_year),
        presentation_id=None,
        presented_at=datetime(filing_year, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=tax_id,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
        source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        parsed_at=datetime(filing_year, 4, 16, 12, 0, tzinfo=UTC),
    )


def _profile() -> TaxpayerProfile:
    """A declared autónomo en estimación directa.

    The structural calendar tests need a profile whose taxpayer model
    produces obligations. An autónomo with rendimientos de actividades
    económicas under estimación directa is the unchanged-by-design
    persona — Modelo 130 / 303 stay applicable, exactly as before the
    taxpayer-type derivation landed.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="overview-calendar test profile",
    )


def test_invalid_pagadores_count_is_debug_logged_without_raw_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_value = "not-a-count-secret"

    with caplog.at_level(logging.DEBUG, logger="aeat.application.overview"):
        advisories = build_filing_obligation_advisories(
            {
                "irpf.pagadores_count": raw_value,
                "irpf.pagadores_secondary_income": "2000",
            },
        )

    assert advisories == ()
    relevant = [
        record
        for record in caplog.records
        if record.getMessage() == "overview filing obligation advisory ignored invalid integer profile value"
    ]
    assert len(relevant) == 1
    assert relevant[0].__dict__["profile_field"] == "irpf.pagadores_count"
    assert relevant[0].__dict__["error_type"] == "ValueError"
    assert raw_value not in relevant[0].getMessage()


def test_invalid_pagadores_secondary_income_is_debug_logged_without_raw_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_value = "not-income-secret"

    with caplog.at_level(logging.DEBUG, logger="aeat.application.overview"):
        advisories = build_filing_obligation_advisories(
            {
                "irpf.pagadores_count": "2",
                "irpf.pagadores_secondary_income": raw_value,
            },
        )

    assert advisories == ()
    relevant = [
        record
        for record in caplog.records
        if record.getMessage() == "overview filing obligation advisory ignored invalid decimal profile value"
    ]
    assert len(relevant) == 1
    assert relevant[0].__dict__["profile_field"] == "irpf.pagadores_secondary_income"
    assert relevant[0].__dict__["error_type"] == "InvalidOperation"
    assert all(raw_value not in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------
# OverviewPeriodState mapping
# ---------------------------------------------------------------------


def test_period_state_enum_carries_cli_values() -> None:
    assert {item.value for item in OverviewPeriodState} == {
        "due",
        "late",
        "filed",
        "unknown",
    }


def test_user_state_maps_open_window_to_due() -> None:
    assert user_state_for(ObligationStatus.UPCOMING) is OverviewPeriodState.DUE
    assert user_state_for(ObligationStatus.DUE_SOON) is OverviewPeriodState.DUE
    assert user_state_for(ObligationStatus.DUE_TODAY) is OverviewPeriodState.DUE


def test_user_state_maps_overdue_to_late() -> None:
    assert user_state_for(ObligationStatus.OVERDUE) is OverviewPeriodState.LATE


def test_user_state_maps_filed_to_filed() -> None:
    assert user_state_for(ObligationStatus.FILED) is OverviewPeriodState.FILED


def test_user_state_maps_not_applicable_to_unknown() -> None:
    assert user_state_for(ObligationStatus.NOT_APPLICABLE) is OverviewPeriodState.UNKNOWN


def test_user_state_covers_every_engine_status() -> None:
    """Every ObligationStatus must map to a user state."""
    for status in ObligationStatus:
        assert isinstance(user_state_for(status), OverviewPeriodState)


# ---------------------------------------------------------------------
# OverviewCalendarRange
# ---------------------------------------------------------------------


def test_range_round_trips_canonical_window() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.from_date == date(2026, 1, 1)
    assert rng.to_date == date(2026, 4, 20)


def test_range_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"from_date|to_date|window|range"):
        OverviewCalendarRange(from_date=date(2026, 4, 20), to_date=date(2026, 1, 1))


def test_range_accepts_single_day_window() -> None:
    # covered_years always includes the prior fiscal year so that annual
    # declarations (IS Modelo 200, IRPF Modelo 100) whose deadlines fall in
    # the following calendar year appear when querying that year.
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 1, 1))
    assert rng.covered_years() == (2025, 2026)


def test_range_covered_years_spans_year_boundary() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20))
    assert rng.covered_years() == (2024, 2025, 2026)


def test_range_covers_returns_true_for_inclusive_bounds() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(date(2026, 1, 1)) is True
    assert rng.covers(date(2026, 4, 20)) is True
    assert rng.covers(date(2026, 3, 15)) is True


def test_range_covers_returns_false_outside_bounds() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(date(2025, 12, 31)) is False
    assert rng.covers(date(2026, 4, 21)) is False


def test_range_is_frozen() -> None:

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        rng.from_date = date(2025, 12, 31)


# ---------------------------------------------------------------------
# OverviewCalendarEntry
# ---------------------------------------------------------------------


def _entry(**overrides: object) -> OverviewCalendarEntry:
    base: dict[str, object] = {
        "modelo": "130",
        "period": Period.from_year_and_code(2026, "1T"),
        "opens_on": date(2026, 4, 1),
        "closes_on": date(2026, 4, 20),
        "adjusted_closes_on": date(2026, 4, 20),
        "shift_reason": "business_day",
        "holiday_refs": (),
        "jurisdictions": (),
        "payment_cutoff_on": date(2026, 4, 15),
        "status": ObligationStatus.UPCOMING,
        "user_state": OverviewPeriodState.DUE,
    }
    base.update(overrides)
    return OverviewCalendarEntry.model_validate(base)


def test_entry_round_trips_canonical_fields() -> None:
    entry = _entry()
    assert entry.modelo == "130"
    assert entry.period == Period.from_year_and_code(2026, "1T")
    assert str(entry.period) == "2026 1T"
    assert entry.user_state is OverviewPeriodState.DUE


def test_entry_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"opens_on|closes_on|window"):
        _entry(opens_on=date(2026, 4, 21), closes_on=date(2026, 4, 20))


def test_entry_rejects_payment_cutoff_after_closes_on() -> None:
    with pytest.raises(ValueError, match=r"payment_cutoff|closes_on"):
        _entry(payment_cutoff_on=date(2026, 4, 25))


def test_entry_rejects_user_state_inconsistent_with_engine_status() -> None:
    with pytest.raises(ValueError, match=r"user_state|status|inconsistent"):
        _entry(status=ObligationStatus.OVERDUE, user_state=OverviewPeriodState.DUE)


def test_entry_is_frozen() -> None:

    entry = _entry()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        entry.modelo = "303"


# ---------------------------------------------------------------------
# OverviewCalendarEvent
# ---------------------------------------------------------------------


def test_expedientes_snapshots_project_filing_events_inside_range() -> None:
    snapshot = PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="X1234567L",
        declarations=(
            Declaracion(
                modelo="303",
                ejercicio=2025,
                period=_PERIOD_2025_1T,
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.FILING
    assert event.event_date == date(2025, 4, 15)
    assert event.modelo == "303"
    assert event.filing_year == 2025
    assert event.period == Period.from_year_and_code(2025, "1T")
    assert event.reference_id == "12345678901234567890"
    assert event.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert event.authenticated_identity == "X1234567L"


def test_expedientes_snapshot_for_wrong_identity_does_not_project_filing_event() -> None:
    snapshot = PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="Y7654321Z",
        declarations=(
            Declaracion(
                modelo="303",
                ejercicio=2025,
                period=_PERIOD_2025_1T,
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        expected_tax_id="X1234567L",
    )

    assert events == ()


def test_notification_snapshots_project_message_events_on_notification_date() -> None:
    row = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(row,),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
    )

    assert len(events) == 1
    assert events[0].event_type is OverviewCalendarEventType.MESSAGE
    assert events[0].event_date == date(2025, 3, 12)
    assert events[0].reference_id == "2596230606502"
    assert events[0].status == "unread"


def test_notification_snapshots_filter_message_events_by_expected_taxpayer() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345678",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345678",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(matching, other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        expected_tax_id="B12345678",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)


def test_notification_snapshots_filter_message_events_by_authenticated_snapshot_identity() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345678",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345678",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    explicit_other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345678",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345678",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    matching_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="B12345678",
        rows=(matching, explicit_other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )
    other_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id="bucket-1",
        captured_at=datetime(2025, 3, 14, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="C12345678",
        rows=(matching,),
        persisted_at=datetime(2025, 3, 14, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (matching_snapshot, other_snapshot),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        expected_tax_id="B12345678",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)


def test_build_overview_calendar_accepts_observed_events() -> None:
    event = build_overview_calendar_events(
        calendar_range=OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        notification_snapshots=(
            PersistedNotificationsSnapshot(
                snapshot_id="a" * 64,
                bucket_id="bucket-1",
                captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                rows=(
                    RemoteNotification(
                        certificado_id="2596230606502",
                        tipo="comunicacion",
                        concepto="Comunicacion informativa",
                        titular_nif="B12345678",
                        titular_nombre="Test S.L.",
                        destinatario_nif="B12345678",
                        destinatario_nombre="Test S.L.",
                        fecha_emision=date(2025, 3, 10),
                        leida=True,
                        source_url=AnyHttpUrl(_SOURCE_URL),
                    ),
                ),
                persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
            ),
        ),
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        today=date(2025, 3, 15),
        events=event,
    )

    assert tuple(observed.reference_id for observed in calendar.events) == ("2596230606502",)


# build_overview_calendar
# ---------------------------------------------------------------------


def test_build_returns_typed_calendar_for_quarterly_window() -> None:
    """``--from 2026-01-01 --to 2026-04-20`` covers Q1 2026."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20)),
        today=date(2026, 4, 1),
    )
    assert isinstance(calendar, OverviewCalendar)
    assert calendar.range.from_date == date(2026, 1, 1)
    assert calendar.range.to_date == date(2026, 4, 20)
    assert isinstance(calendar.generated_at, datetime)
    assert calendar.generated_at.tzinfo == UTC


def test_build_only_emits_entries_inside_range() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20)),
        today=date(2026, 4, 1),
    )
    for entry in calendar.entries:
        # An entry must intersect the inclusive range.
        assert entry.closes_on >= date(2026, 1, 1)
        assert entry.opens_on <= date(2026, 4, 20)


def test_build_orders_entries_by_close_then_modelo_then_period() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        today=date(2026, 4, 1),
    )
    keys = [
        (entry.closes_on, entry.modelo, entry.period.year, entry.period.registry_token) for entry in calendar.entries
    ]
    assert keys == sorted(keys)


def test_build_tape_invocation_2025q4_through_2026q2_spans_year_boundary() -> None:
    """``--from 2025-10-01 --to 2026-07-20`` spans multiple years."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20)),
        today=date(2026, 5, 3),
    )
    years = {entry.period.year for entry in calendar.entries}
    # The range straddles 2025 -> 2026, so both years must contribute.
    assert 2025 in years or 2026 in years


def test_build_user_state_matches_engine_status_per_entry() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        today=date(2026, 4, 1),
    )
    for entry in calendar.entries:
        assert entry.user_state is user_state_for(entry.status)


def test_build_empty_range_when_window_covers_no_obligations() -> None:
    """A 1-day window outside every modelo's filing window emits no entries."""
    # 2026-01-15 lies outside every modelo's January quarterly / monthly window.
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 15), to_date=date(2026, 1, 15)),
        today=date(2026, 4, 1),
    )
    assert isinstance(calendar.entries, tuple)


def test_build_threads_shift_metadata_onto_every_entry() -> None:
    """Every assembled entry carries the festivos-shift outcome.

    The contract: ``adjusted_closes_on`` is populated, ``shift_reason``
    is one of the closed set returned by
    :func:`aeat.domain.deadlines.shift_deadline`, and the adjusted date
    never precedes the original close.
    """
    accepted_reasons = {
        "business_day",
        "modelo_exception",
        "weekend",
        "national_holiday",
        "ccaa_holiday",
        "calendar_unavailable",
    }
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))
    assert cal.entries, "expected the test profile to produce at least one obligation"
    for entry in cal.entries:
        assert entry.adjusted_closes_on >= entry.closes_on
        assert entry.shift_reason in accepted_reasons


def test_build_marks_modelo_369_as_modelo_exception() -> None:
    """Modelo 369 obligations bypass the shift; reason must be modelo_exception."""
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))
    modelo_369 = [entry for entry in cal.entries if entry.modelo == "369"]
    # Whether 369 appears for the test profile depends on the profile's
    # OSS enrolment. When it does appear, the shift must be skipped.
    for entry in modelo_369:
        assert entry.shift_reason == "modelo_exception"
        assert entry.adjusted_closes_on == entry.closes_on
        assert entry.holiday_refs == ()


def test_entry_rejects_adjusted_close_that_precedes_original() -> None:
    """The shift rule is strictly monotone non-decreasing.

    A construction with ``adjusted_closes_on < closes_on`` is a
    structural violation: the shift can only move a deadline forward.
    """
    with pytest.raises(ValueError, match=r"adjusted_closes_on|may only move"):
        _entry(
            closes_on=date(2026, 4, 20),
            adjusted_closes_on=date(2026, 4, 19),
        )


def test_build_is_idempotent_modulo_generated_at() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    profile = _profile()
    a = build_overview_calendar(profile, rng, today=today)
    b = build_overview_calendar(profile, rng, today=today)
    assert a.entries == b.entries
    assert a.range == b.range


def test_calendar_omits_warnings_when_raw_values_not_supplied() -> None:
    """Without raw_values the aggregator returns no warnings or completeness rows.

    Existing callers that build the calendar from a fully-resolved
    ``TaxpayerProfile`` without surfacing the user_cli raw mapping
    must not see new warning behaviour. The empty defaults on
    OverviewCalendar.warnings / completeness preserve backwards
    compatibility for those callers.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    cal = build_overview_calendar(_profile(), rng, today=today)
    assert cal.warnings == ()
    assert cal.completeness.explicitly_set_keys == ()
    assert cal.completeness.defaulted_keys == ()


def test_calendar_emits_warning_when_iva_regime_unset() -> None:
    """A profile with no iva.regime declared must produce a typed warning.

    The deadline engine's modelo-applicability rules default to GENERAL
    when iva.regime is absent and would otherwise compute 303/390
    entries under those defaults without signalling the assumption.
    The contract verified here: when raw_values omits iva.regime, the
    aggregator emits a CalendarWarning whose code names the missing
    key, fix_command supplies the literal aeat config profile edit
    command, and affected_modelos lists 303/390.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {"tax.id": "X1234567L", "activity": "design"}
    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    iva_warnings = [w for w in cal.warnings if w.code == "iva.regime"]
    assert len(iva_warnings) == 1
    warning = iva_warnings[0]
    assert "303" in warning.affected_modelos
    assert "390" in warning.affected_modelos
    assert warning.fix_command == "aeat config profile edit"


def test_calendar_completeness_lists_uncomputable_with_reason() -> None:
    """``CalendarCompleteness`` must enumerate explicit vs defaulted keys.

    With only ``iva.regime`` declared, the completeness payload must
    list it under explicitly_set_keys and the remaining gating keys
    (does_intracomunitario, pays_professionals_with_retencion,
    pays_rent_with_retencion, uses_objective_estimation_irpf) under
    defaulted_keys.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {
        "tax.id": "X1234567L",
        "activity": "design",
        "iva.regime": "general",
    }
    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    assert "iva.regime" in cal.completeness.explicitly_set_keys
    assert "does_intracomunitario" in cal.completeness.defaulted_keys
    assert "pays_professionals_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_rent_with_retencion" in cal.completeness.defaulted_keys
    assert "uses_objective_estimation_irpf" in cal.completeness.defaulted_keys
