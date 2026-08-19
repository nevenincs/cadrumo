"""Tests for censo modelo foundation ownership."""

from __future__ import annotations

import logging
from typing import Any, cast

import pytest
from pydantic import ValidationError

from .....core.errors import get_registered_error_code
from .....core.resources import resources
from .. import (
    CENSO_MODELO_ERROR_CODES,
    CENSO_MODELO_EVENT_KINDS,
    CENSO_MODELO_SERVICE_OWNER,
    CensoModeloEventKind,
    CensoModeloFoundationCommand,
    CensoModeloFoundationLogFields,
    CensoModeloFoundationResult,
    CensoModeloRole,
    RegistrySnapshotError,
    RegistryValidationError,
    censo_modelo_ownership,
    censo_modelo_ownership_map,
    get_censo_modelo_foundation_contract,
    is_active_censo_modelo,
    resolve_censo_modelo_foundation,
    resolve_censo_modelo_work_unit_foundation,
    select_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def _m036_2025_alta_revision():
    """The revision modelo 036's `alta` event resolves to, selected not snapshotted.

    Both cases below read revision-level facts -- the period selector and the
    filing schedule. `authority.snapshot` takes no grade and always builds at the
    FILING rung, so it demanded a reviewed revision and filing capability from
    modelo 036, whose registry declares `authority_grade = applicability`: a
    censal alta/modificacion/baja is filed on AEAT's sede and this application
    produces no fichero for it.

    `select_revision` is the sanctioned resolver for "which revision governs this
    period" and keeps the teeth -- a period no revision declares still raises.
    """
    authority = resources().modelos.authority
    return select_revision(authority.validate_modelo("036"), filing_year=2025, period="alta")


def test_censo_foundation_owner_is_registry_domain() -> None:
    records = censo_modelo_ownership_map()

    assert {record.modelo for record in records} == {"036", "037"}
    assert {record.service_owner for record in records} == {CENSO_MODELO_SERVICE_OWNER}
    assert CENSO_MODELO_SERVICE_OWNER == "cadrumo.domain.calculations.registry"


def test_censo_foundation_contract_records_service_error_codes() -> None:
    contract = get_censo_modelo_foundation_contract()

    assert contract.schema_version == "1"
    assert contract.service_owner == CENSO_MODELO_SERVICE_OWNER
    assert contract.active_modelo == "036"
    assert contract.historical_modelos == ("037",)
    assert contract.event_kinds == tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS)
    assert contract.error_codes == CENSO_MODELO_ERROR_CODES
    assert CENSO_MODELO_ERROR_CODES == ("ERROR_CALCULATIONS_REGISTRY_VALIDATION",)
    assert get_registered_error_code(RegistryValidationError).code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"


def test_modelo_036_is_active_event_triggered_foundation() -> None:
    record = censo_modelo_ownership("036")

    assert record.role is CensoModeloRole.ACTIVE_FOUNDATION
    assert record.event_kinds == CENSO_MODELO_EVENT_KINDS
    assert record.event_kinds == ("alta", "modificacion", "baja")
    assert record.active_work_unit_allowed is True
    assert record.superseded_by is None
    assert is_active_censo_modelo("036") is True


def test_modelo_036_foundation_event_kinds_are_registry_backed(_m036_2025_alta_revision) -> None:
    record = censo_modelo_ownership("036")
    revision = _m036_2025_alta_revision
    schedules = {schedule.id: schedule for schedule in revision.filing_schedules}

    assert record.event_kinds == revision.period_selector.periods
    assert schedules["modelo-036-event-triggered"].periods == record.event_kinds


def test_active_036_work_unit_periods_resolve_from_committed_registry_revision(
    _m036_2025_alta_revision,
) -> None:
    revision = _m036_2025_alta_revision

    for period in revision.period_selector.periods:
        result = resolve_censo_modelo_work_unit_foundation(modelo="036", period=period)

        assert result is not None
        assert result.modelo == "036"
        assert result.event_kind is CensoModeloEventKind(period)
        expected_event_kinds = tuple(CensoModeloEventKind(kind) for kind in revision.period_selector.periods)
        assert result.event_kinds == expected_event_kinds


def test_modelo_037_is_historical_metadata_superseded_by_036() -> None:
    record = censo_modelo_ownership("037")

    assert record.role is CensoModeloRole.HISTORICAL_METADATA
    assert record.event_kinds == ()
    assert record.active_work_unit_allowed is False
    assert record.superseded_by == "036"
    assert is_active_censo_modelo("037") is False


def test_modelo_145_registry_presence_does_not_change_censo_036_037_contracts() -> None:
    authority = resources().modelos.authority
    modelo_145_snapshot = authority.snapshot("145", filing_year=2026, period="comunicacion")
    active_036 = resolve_censo_modelo_work_unit_foundation(modelo="036", period="alta")
    historical_037 = resolve_censo_modelo_foundation(CensoModeloFoundationCommand(modelo="037"))

    assert modelo_145_snapshot.modelo.id == "145"
    assert active_036 is not None
    assert active_036.modelo == "036"
    assert active_036.role is CensoModeloRole.ACTIVE_FOUNDATION
    assert active_036.event_kind is CensoModeloEventKind.ALTA
    assert active_036.event_kinds == tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS)
    assert active_036.active_work_unit_allowed is True
    assert active_036.superseded_by is None
    assert historical_037.modelo == "037"
    assert historical_037.role is CensoModeloRole.HISTORICAL_METADATA
    assert historical_037.event_kind is None
    assert historical_037.event_kinds == ()
    assert historical_037.active_work_unit_allowed is False
    assert historical_037.superseded_by == "036"
    with pytest.raises(RegistrySnapshotError, match="not present in the calculation registry"):
        authority.validate_modelo("037")


def test_historical_037_contract_is_proven_by_registry_absence_and_suppression_source() -> None:
    authority = resources().modelos.authority

    with pytest.raises(RegistrySnapshotError, match="not present in the calculation registry"):
        authority.validate_modelo("037")

    assert "boe-modelo-037-historical-suppression" in authority.catalogues.sources
    record = censo_modelo_ownership("037")
    assert record.role is CensoModeloRole.HISTORICAL_METADATA
    assert record.active_work_unit_allowed is False
    assert record.superseded_by == "036"


def test_censo_modelo_lookup_rejects_shortened_aliases() -> None:
    for modelo in ("36", "37", " 36 ", " 37 ", " 036 ", " 037 "):
        with pytest.raises(RegistryValidationError, match="unknown censo modelo code"):
            censo_modelo_ownership(modelo)


def test_censo_modelo_lookup_rejects_integer_codes() -> None:
    not_a_string = cast(Any, 36)
    with pytest.raises(RegistryValidationError, match="must be a string"):
        censo_modelo_ownership(not_a_string)


def test_censo_foundation_command_accepts_active_036_event_kind() -> None:
    command = CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.ALTA)

    assert command.modelo == "036"
    assert command.event_kind is CensoModeloEventKind.ALTA
    with pytest.raises(ValidationError, match="frozen"):
        command.modelo = "037"


def test_censo_foundation_command_rejects_missing_event_for_036() -> None:
    with pytest.raises(ValidationError, match="requires event_kind"):
        CensoModeloFoundationCommand(modelo="036")


def test_censo_foundation_command_rejects_active_event_for_037() -> None:
    with pytest.raises(ValidationError, match="must not declare event_kind"):
        CensoModeloFoundationCommand(modelo="037", event_kind=CensoModeloEventKind.BAJA)


def test_censo_foundation_command_accepts_inactive_037_without_event_kind() -> None:
    command = CensoModeloFoundationCommand(modelo="037")

    assert command.modelo == "037"
    assert command.event_kind is None


def test_censo_foundation_command_rejects_unknown_event_kind() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        CensoModeloFoundationCommand.model_validate({"modelo": "036", "event_kind": "altaa"})


def test_censo_foundation_command_rejects_alias_and_integer_codes() -> None:
    for payload in ({"modelo": "36"}, {"modelo": " 036 "}, {"modelo": 36}):
        with pytest.raises(ValidationError):
            CensoModeloFoundationCommand.model_validate({**payload, "event_kind": "alta"})


def test_censo_foundation_result_accepts_active_036_decision() -> None:
    result = CensoModeloFoundationResult(
        modelo="036",
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        event_kind=CensoModeloEventKind.MODIFICACION,
        event_kinds=tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS),
        active_work_unit_allowed=True,
    )

    assert result.modelo == "036"
    assert result.event_kind is CensoModeloEventKind.MODIFICACION
    assert result.superseded_by is None


def test_censo_foundation_result_accepts_historical_037_decision() -> None:
    result = CensoModeloFoundationResult(
        modelo="037",
        role=CensoModeloRole.HISTORICAL_METADATA,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        active_work_unit_allowed=False,
        superseded_by="036",
    )

    assert result.modelo == "037"
    assert result.event_kind is None
    assert result.event_kinds == ()


def test_censo_foundation_result_rejects_active_037_work_unit() -> None:
    with pytest.raises(ValidationError, match="inactive and superseded by 036"):
        CensoModeloFoundationResult(
            modelo="037",
            role=CensoModeloRole.HISTORICAL_METADATA,
            service_owner=CENSO_MODELO_SERVICE_OWNER,
            active_work_unit_allowed=True,
            superseded_by="036",
        )


def test_resolve_censo_modelo_foundation_returns_active_036_decision() -> None:
    result = resolve_censo_modelo_foundation(
        CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.BAJA),
    )

    assert result.modelo == "036"
    assert result.role is CensoModeloRole.ACTIVE_FOUNDATION
    assert result.service_owner == CENSO_MODELO_SERVICE_OWNER
    assert result.event_kind is CensoModeloEventKind.BAJA
    assert result.event_kinds == tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS)
    assert result.active_work_unit_allowed is True
    assert result.superseded_by is None
    assert result.log_fields.as_extra() == {
        "service_name": "censo_modelo_foundation",
        "service_owner": CENSO_MODELO_SERVICE_OWNER,
        "modelo": "036",
        "role": "active_foundation",
        "decision": "active_work_unit_allowed",
        "event_kind": "baja",
        "active_work_unit_allowed": True,
        "superseded_by": "",
    }


def test_resolve_censo_modelo_foundation_returns_historical_037_decision() -> None:
    result = resolve_censo_modelo_foundation(CensoModeloFoundationCommand(modelo="037"))

    assert result.modelo == "037"
    assert result.role is CensoModeloRole.HISTORICAL_METADATA
    assert result.event_kind is None
    assert result.event_kinds == ()
    assert result.active_work_unit_allowed is False
    assert result.superseded_by == "036"
    assert result.log_fields.as_extra() == {
        "service_name": "censo_modelo_foundation",
        "service_owner": CENSO_MODELO_SERVICE_OWNER,
        "modelo": "037",
        "role": "historical_metadata",
        "decision": "historical_metadata_only",
        "event_kind": "",
        "active_work_unit_allowed": False,
        "superseded_by": "036",
    }


def test_resolve_censo_modelo_work_unit_foundation_routes_active_censo_modelo() -> None:
    active = resolve_censo_modelo_work_unit_foundation(modelo="036", period="alta")

    assert active is not None
    assert active.modelo == "036"
    assert active.event_kind is CensoModeloEventKind.ALTA


def test_resolve_censo_modelo_work_unit_foundation_rejects_historical_037() -> None:
    with pytest.raises(RegistryValidationError, match="historical censo metadata only"):
        resolve_censo_modelo_work_unit_foundation(modelo="037", period="alta")


def test_resolve_censo_modelo_work_unit_foundation_rejects_censo_code_aliases() -> None:
    for modelo in ("36", "37", " 36 ", " 37 ", " 036 ", " 037 "):
        with pytest.raises(RegistryValidationError, match="unknown censo modelo code"):
            resolve_censo_modelo_work_unit_foundation(modelo=modelo, period="alta")


def test_resolve_censo_modelo_work_unit_foundation_ignores_non_censo_modelo() -> None:
    assert resolve_censo_modelo_work_unit_foundation(modelo="303", period="1T") is None


def test_resolve_censo_modelo_work_unit_foundation_rejects_non_string_modelo() -> None:
    not_a_string = cast(Any, 303)
    with pytest.raises(RegistryValidationError, match="must be a string"):
        resolve_censo_modelo_work_unit_foundation(modelo=not_a_string, period="1T")


def test_resolve_censo_modelo_work_unit_foundation_rejects_unknown_censo_period() -> None:
    with pytest.raises(RegistryValidationError, match="censo event periods"):
        resolve_censo_modelo_work_unit_foundation(modelo="036", period="1T")


def test_censo_foundation_log_fields_are_strict_and_immutable() -> None:
    log_fields = CensoModeloFoundationLogFields(
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        modelo="036",
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        decision="active_work_unit_allowed",
        event_kind=CensoModeloEventKind.ALTA,
        active_work_unit_allowed=True,
    )

    assert log_fields.as_extra()["event_kind"] == "alta"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CensoModeloFoundationLogFields.model_validate(
            {
                "service_owner": CENSO_MODELO_SERVICE_OWNER,
                "modelo": "036",
                "role": CensoModeloRole.ACTIVE_FOUNDATION,
                "decision": "active_work_unit_allowed",
                "event_kind": CensoModeloEventKind.ALTA,
                "active_work_unit_allowed": True,
                "unexpected": "field",
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        log_fields.modelo = "037"


def test_resolve_censo_modelo_foundation_emits_structured_debug_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="cadrumo.domain.calculations.registry._censo_modelos")

    resolve_censo_modelo_foundation(
        CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.MODIFICACION),
    )

    record = next(
        log_record for log_record in caplog.records if log_record.getMessage() == "resolved censo modelo foundation"
    )
    log_extra = vars(record)
    assert log_extra["service_name"] == "censo_modelo_foundation"
    assert log_extra["service_owner"] == CENSO_MODELO_SERVICE_OWNER
    assert log_extra["modelo"] == "036"
    assert log_extra["role"] == "active_foundation"
    assert log_extra["event_kind"] == "modificacion"
    assert log_extra["decision"] == "active_work_unit_allowed"
    assert log_extra["active_work_unit_allowed"] is True
    assert log_extra["superseded_by"] == ""
