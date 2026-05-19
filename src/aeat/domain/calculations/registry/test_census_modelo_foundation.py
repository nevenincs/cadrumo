"""Tests for census modelo foundation ownership."""

from __future__ import annotations
from aeat.core.resources import resources

import logging
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core.errors import get_registered_error_code
from . import (
    CENSUS_MODELO_ERROR_CODES,
    CENSUS_MODELO_EVENT_KINDS,
    CENSUS_MODELO_SERVICE_OWNER,
    CensoModeloEventKind,
    CensoModeloFoundationCommand,
    CensoModeloFoundationLogFields,
    CensoModeloFoundationResult,
    CensoModeloRole,
    RegistrySnapshotError,
    RegistryValidationError,
    census_modelo_ownership,
    census_modelo_ownership_map,
    get_census_modelo_foundation_contract,
    is_active_census_modelo,
    resolve_census_modelo_foundation,
    resolve_census_modelo_work_unit_foundation,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_census_foundation_owner_is_registry_domain() -> None:
    records = census_modelo_ownership_map()

    assert {record.modelo for record in records} == {"036", "037"}
    assert {record.service_owner for record in records} == {CENSUS_MODELO_SERVICE_OWNER}
    assert CENSUS_MODELO_SERVICE_OWNER == "aeat.domain.calculations.registry"


def test_census_foundation_contract_records_service_error_codes() -> None:
    contract = get_census_modelo_foundation_contract()

    assert contract.schema_version == "1"
    assert contract.service_owner == CENSUS_MODELO_SERVICE_OWNER
    assert contract.active_modelo == "036"
    assert contract.historical_modelos == ("037",)
    assert contract.event_kinds == tuple(CensoModeloEventKind(kind) for kind in CENSUS_MODELO_EVENT_KINDS)
    assert contract.error_codes == CENSUS_MODELO_ERROR_CODES
    assert CENSUS_MODELO_ERROR_CODES == ("ERROR_CALCULATIONS_REGISTRY_VALIDATION",)
    assert get_registered_error_code(RegistryValidationError).code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"


def test_modelo_036_is_active_event_triggered_foundation() -> None:
    record = census_modelo_ownership("036")

    assert record.role is CensoModeloRole.ACTIVE_FOUNDATION
    assert record.event_kinds == CENSUS_MODELO_EVENT_KINDS
    assert record.event_kinds == ("alta", "modificacion", "baja")
    assert record.active_work_unit_allowed is True
    assert record.superseded_by is None
    assert is_active_census_modelo("036") is True


def test_modelo_036_foundation_event_kinds_are_registry_backed() -> None:
    record = census_modelo_ownership("036")
    snapshot = resources().modelos.authority.snapshot("036", filing_year=2025, period="alta")

    assert record.event_kinds == snapshot.revision.period_selector.periods
    assert snapshot.filing_schedules["modelo-036-event-triggered"].periods == record.event_kinds


def test_active_036_work_unit_periods_resolve_from_committed_registry_revision() -> None:
    snapshot = resources().modelos.authority.snapshot("036", filing_year=2025, period="alta")

    for period in snapshot.revision.period_selector.periods:
        result = resolve_census_modelo_work_unit_foundation(modelo="036", period=period)

        assert result is not None
        assert result.modelo == "036"
        assert result.event_kind is CensoModeloEventKind(period)
        expected_event_kinds = tuple(CensoModeloEventKind(kind) for kind in snapshot.revision.period_selector.periods)
        assert result.event_kinds == expected_event_kinds


def test_modelo_037_is_historical_metadata_superseded_by_036() -> None:
    record = census_modelo_ownership("037")

    assert record.role is CensoModeloRole.HISTORICAL_METADATA
    assert record.event_kinds == ()
    assert record.active_work_unit_allowed is False
    assert record.superseded_by == "036"
    assert is_active_census_modelo("037") is False


def test_historical_037_contract_is_proven_by_registry_absence_and_suppression_source() -> None:
    authority = resources().modelos.authority

    with pytest.raises(RegistrySnapshotError):
        authority.validate_modelo("037")

    assert "boe-modelo-037-historical-suppression" in authority.catalogues.sources
    record = census_modelo_ownership("037")
    assert record.role is CensoModeloRole.HISTORICAL_METADATA
    assert record.active_work_unit_allowed is False
    assert record.superseded_by == "036"


@pytest.mark.parametrize("modelo", ["36", "37", " 36 ", " 37 ", " 036 ", " 037 "])
def test_census_modelo_lookup_rejects_shortened_aliases(modelo: str) -> None:
    with pytest.raises(RegistryValidationError, match="unknown census modelo code"):
        census_modelo_ownership(modelo)


def test_census_modelo_lookup_rejects_integer_codes() -> None:
    not_a_string = cast(Any, 36)
    with pytest.raises(RegistryValidationError, match="must be a string"):
        census_modelo_ownership(not_a_string)


def test_census_foundation_command_accepts_active_036_event_kind() -> None:
    command = CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.ALTA)

    assert command.modelo == "036"
    assert command.event_kind is CensoModeloEventKind.ALTA
    with pytest.raises(ValidationError, match="frozen"):
        command.modelo = "037"


def test_census_foundation_command_rejects_missing_event_for_036() -> None:
    with pytest.raises(ValidationError, match="requires event_kind"):
        CensoModeloFoundationCommand(modelo="036")


def test_census_foundation_command_rejects_active_event_for_037() -> None:
    with pytest.raises(ValidationError, match="must not declare event_kind"):
        CensoModeloFoundationCommand(modelo="037", event_kind=CensoModeloEventKind.BAJA)


def test_census_foundation_command_accepts_inactive_037_without_event_kind() -> None:
    command = CensoModeloFoundationCommand(modelo="037")

    assert command.modelo == "037"
    assert command.event_kind is None


def test_census_foundation_command_rejects_unknown_event_kind() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        CensoModeloFoundationCommand.model_validate({"modelo": "036", "event_kind": "altaa"})


@pytest.mark.parametrize("payload", [{"modelo": "36"}, {"modelo": " 036 "}, {"modelo": 36}])
def test_census_foundation_command_rejects_alias_and_integer_codes(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CensoModeloFoundationCommand.model_validate({**payload, "event_kind": "alta"})


def test_census_foundation_result_accepts_active_036_decision() -> None:
    result = CensoModeloFoundationResult(
        modelo="036",
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSUS_MODELO_SERVICE_OWNER,
        event_kind=CensoModeloEventKind.MODIFICACION,
        event_kinds=tuple(CensoModeloEventKind(kind) for kind in CENSUS_MODELO_EVENT_KINDS),
        active_work_unit_allowed=True,
    )

    assert result.modelo == "036"
    assert result.event_kind is CensoModeloEventKind.MODIFICACION
    assert result.superseded_by is None


def test_census_foundation_result_accepts_historical_037_decision() -> None:
    result = CensoModeloFoundationResult(
        modelo="037",
        role=CensoModeloRole.HISTORICAL_METADATA,
        service_owner=CENSUS_MODELO_SERVICE_OWNER,
        active_work_unit_allowed=False,
        superseded_by="036",
    )

    assert result.modelo == "037"
    assert result.event_kind is None
    assert result.event_kinds == ()


def test_census_foundation_result_rejects_active_037_work_unit() -> None:
    with pytest.raises(ValidationError, match="inactive and superseded by 036"):
        CensoModeloFoundationResult(
            modelo="037",
            role=CensoModeloRole.HISTORICAL_METADATA,
            service_owner=CENSUS_MODELO_SERVICE_OWNER,
            active_work_unit_allowed=True,
            superseded_by="036",
        )


def test_resolve_census_modelo_foundation_returns_active_036_decision() -> None:
    result = resolve_census_modelo_foundation(
        CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.BAJA)
    )

    assert result.modelo == "036"
    assert result.role is CensoModeloRole.ACTIVE_FOUNDATION
    assert result.service_owner == CENSUS_MODELO_SERVICE_OWNER
    assert result.event_kind is CensoModeloEventKind.BAJA
    assert result.event_kinds == tuple(CensoModeloEventKind(kind) for kind in CENSUS_MODELO_EVENT_KINDS)
    assert result.active_work_unit_allowed is True
    assert result.superseded_by is None
    assert result.log_fields.as_extra() == {
        "service_name": "census_modelo_foundation",
        "service_owner": CENSUS_MODELO_SERVICE_OWNER,
        "modelo": "036",
        "role": "active_foundation",
        "decision": "active_work_unit_allowed",
        "event_kind": "baja",
        "active_work_unit_allowed": True,
        "superseded_by": "",
    }


def test_resolve_census_modelo_foundation_returns_historical_037_decision() -> None:
    result = resolve_census_modelo_foundation(CensoModeloFoundationCommand(modelo="037"))

    assert result.modelo == "037"
    assert result.role is CensoModeloRole.HISTORICAL_METADATA
    assert result.event_kind is None
    assert result.event_kinds == ()
    assert result.active_work_unit_allowed is False
    assert result.superseded_by == "036"
    assert result.log_fields.as_extra() == {
        "service_name": "census_modelo_foundation",
        "service_owner": CENSUS_MODELO_SERVICE_OWNER,
        "modelo": "037",
        "role": "historical_metadata",
        "decision": "historical_metadata_only",
        "event_kind": "",
        "active_work_unit_allowed": False,
        "superseded_by": "036",
    }


def test_resolve_census_modelo_work_unit_foundation_routes_active_census_modelo() -> None:
    active = resolve_census_modelo_work_unit_foundation(modelo="036", period="alta")

    assert active is not None
    assert active.modelo == "036"
    assert active.event_kind is CensoModeloEventKind.ALTA


def test_resolve_census_modelo_work_unit_foundation_rejects_historical_037() -> None:
    with pytest.raises(RegistryValidationError, match="historical census metadata only"):
        resolve_census_modelo_work_unit_foundation(modelo="037", period="alta")


@pytest.mark.parametrize("modelo", ["36", "37", " 36 ", " 37 ", " 036 ", " 037 "])
def test_resolve_census_modelo_work_unit_foundation_rejects_census_code_aliases(modelo: str) -> None:
    with pytest.raises(RegistryValidationError, match="unknown census modelo code"):
        resolve_census_modelo_work_unit_foundation(modelo=modelo, period="alta")


def test_resolve_census_modelo_work_unit_foundation_ignores_non_census_modelo() -> None:
    assert resolve_census_modelo_work_unit_foundation(modelo="303", period="1T") is None


def test_resolve_census_modelo_work_unit_foundation_rejects_non_string_modelo() -> None:
    not_a_string = cast(Any, 303)
    with pytest.raises(RegistryValidationError, match="must be a string"):
        resolve_census_modelo_work_unit_foundation(modelo=not_a_string, period="1T")


def test_resolve_census_modelo_work_unit_foundation_rejects_unknown_census_period() -> None:
    with pytest.raises(RegistryValidationError, match="census event periods"):
        resolve_census_modelo_work_unit_foundation(modelo="036", period="1T")


def test_census_foundation_log_fields_are_strict_and_immutable() -> None:
    log_fields = CensoModeloFoundationLogFields(
        service_owner=CENSUS_MODELO_SERVICE_OWNER,
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
                "service_owner": CENSUS_MODELO_SERVICE_OWNER,
                "modelo": "036",
                "role": CensoModeloRole.ACTIVE_FOUNDATION,
                "decision": "active_work_unit_allowed",
                "event_kind": CensoModeloEventKind.ALTA,
                "active_work_unit_allowed": True,
                "unexpected": "field",
            }
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        log_fields.modelo = "037"


def test_resolve_census_modelo_foundation_emits_structured_debug_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="aeat.domain.calculations.registry._censo_modelos")

    resolve_census_modelo_foundation(
        CensoModeloFoundationCommand(modelo="036", event_kind=CensoModeloEventKind.MODIFICACION)
    )

    record = next(
        log_record for log_record in caplog.records if log_record.getMessage() == "resolved census modelo foundation"
    )
    log_extra = vars(record)
    assert log_extra["service_name"] == "census_modelo_foundation"
    assert log_extra["service_owner"] == CENSUS_MODELO_SERVICE_OWNER
    assert log_extra["modelo"] == "036"
    assert log_extra["role"] == "active_foundation"
    assert log_extra["event_kind"] == "modificacion"
    assert log_extra["decision"] == "active_work_unit_allowed"
    assert log_extra["active_work_unit_allowed"] is True
    assert log_extra["superseded_by"] == ""
