"""Focused public disclosure and scope checks for persisted expediente reads."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..expedientes import PersistedExpedientesSnapshot
from ..expedientes_ports import ExpedientesDeclaration, ExpedientesPorts
from ..expedientes_read_operation import (
    EXPEDIENTES_SHOW_DEFINITION_ID,
    ExpedientesShowOperationReport,
    ExpedientesShowPublicResultV1,
    ExpedientesShowRequest,
    build_expedientes_show_definition,
    build_expedientes_show_registration,
    resolve_expedientes_show_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("11111111-1111-4111-8111-111111111111")
_OTHER_PROFILE = UUID("22222222-2222-4222-8222-222222222222")
_NOW = datetime(2025, 4, 15, 10, tzinfo=UTC)


def _registration():
    def unused_ports(*, bucket_id: str) -> ExpedientesPorts:
        raise AssertionError(f"executor unexpectedly composed ports for {bucket_id}")

    definition = build_expedientes_show_definition(unused_ports)
    return build_expedientes_show_registration(definition)


def _receipt(*, effect: OperationEffect = OperationEffect.NONE) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=_NOW,
        result_ref="result-ref",
    )


def test_show_projection_preserves_period_and_all_existing_declaration_fields() -> None:
    declaration = ExpedientesDeclaration(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        estado="ALTA",
        tipo_solicitud="Presentación",
        observaciones="Synthetic reference",
        presented_at=_NOW,
        justificante_link_text="Justificante",
        archive_link_text="Archivo",
        declaration_copy_link_text="Copia",
        justificante_cell_index=7,
        archive_cell_index=8,
        declaration_copy_cell_index=9,
    )
    report = ExpedientesShowOperationReport(
        snapshot=PersistedExpedientesSnapshot(
            snapshot_id="b" * 64,
            bucket_id=str(_PROFILE),
            captured_at=_NOW,
            source_url="https://sede.example/expedientes",
            authenticated_identity="12345678Z",
            declarations=(declaration,),
            persisted_at=_NOW,
        )
    )
    projector = _registration().result_projector
    assert projector is not None

    result = projector(report, _receipt())

    assert isinstance(result, ExpedientesShowPublicResultV1)
    assert result.declaration_count == 1
    assert result.declarations[0].period == declaration.period.registry_token
    assert result.declarations[0].observaciones == "Synthetic reference"
    assert result.declarations[0].declaration_copy_cell_index == 9
    assert set(result.declarations[0].model_dump()) == {
        "modelo",
        "ejercicio",
        "period",
        "expediente_id",
        "estado",
        "tipo_solicitud",
        "observaciones",
        "presented_at",
        "justificante_link_text",
        "archive_link_text",
        "declaration_copy_link_text",
        "justificante_cell_index",
        "archive_cell_index",
        "declaration_copy_cell_index",
        "mode",
    }
    with pytest.raises(ValueError, match="terminal receipt"):
        projector(report, _receipt(effect=OperationEffect.UPDATED))


def test_show_access_requires_exact_profile_and_whole_profile_disclosure() -> None:
    registration = _registration()
    request = OperationRequest(
        definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ExpedientesShowRequest(profile_id=_PROFILE, snapshot_id="b" * 8),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    access = resolve_expedientes_show_access(request, context)

    assert access.request.period_independent
    assert access.policy.requires_all_periods
    foreign = request.model_copy(
        update={"payload": ExpedientesShowRequest(profile_id=_OTHER_PROFILE, snapshot_id="b" * 8)}
    )
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_expedientes_show_access(foreign, context)
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
