"""Maritime operation scope, canonical result preservation and typed refusals."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.renta.maritime_exemption import MaritimeExemptionInactiveError, MaritimeWorkerFacts
from ...calculations.maritime_exemption_service import resolve_maritime_exemption
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.capabilities import OperationRequestStoragePolicy
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, DisclosureCategory
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..maritime_preview import ModeloMaritimeExemptionPreview, preview_maritime_exemption_for_active_profile
from ..maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    ModeloMaritimePreviewPorts,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
    build_modelo_maritime_preview_definition,
    build_modelo_maritime_preview_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000ab")


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _phase: str) -> None:
        pass

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.rows: list[BaseModel] = []

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.rows.append(operand)
        return "f" * 64


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("refused maritime request must not construct or invoke a service")


def _request(payload: ModeloMaritimePreviewRequest) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(payload.profile_id)),
        payload=payload,
    )


def _context(
    request: OperationRequest[BaseModel], operation: PinnedAuthorityOperation, events: _Events, operands: _Operands
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
                ),
                authority_operation=operation,
                events=events,
                operands=operands,
            ),
        ),
    )


def test_maritime_schema_compiles_and_only_admits_its_period_independent_profile_read(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    definition = build_modelo_maritime_preview_definition(_unavailable)
    registration = build_modelo_maritime_preview_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert len(registry.lookup_public_registration(definition.definition_id).schema_bindings) == 2
    request = _request(ModeloMaritimePreviewRequest(profile_id=_PROFILE))
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert not resolved.request.periods and resolved.request.period_independent
    assert resolved.policy.allow_period_independent and not resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions
    assert {row.category for row in resolved.policy.disclosures} == {DisclosureCategory.TAX_VALUES}
    foreign = _request(ModeloMaritimePreviewRequest(profile_id=uuid4()))
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=foreign, context=context)
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize("value", ["1e3", "+36500", "36.500", "36.500,00", "36500,00", "3 6500", "NaN", "Infinity"])
def test_maritime_wire_inputs_reuse_the_original_canonical_euro_grammar(value: str) -> None:
    with pytest.raises(ValidationError):
        ModeloMaritimePreviewRequest(profile_id=_PROFILE, annual_salary=value)


@pytest.mark.parametrize("pathway", ["art7p", "rebeca", "none", "retmar"])
def test_maritime_worker_preserves_canonical_observations_original_facts_and_warning(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, pathway: str
) -> None:
    events, operands = _Events(), _Operands()
    facts = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar" if pathway != "none" else None,
        vessel_flag="foreign" if pathway == "art7p" else None,
        vessel_registry="REBECA" if pathway in {"rebeca", "retmar"} else None,
        retmar_registered=pathway == "retmar",
    )
    monkeypatch.setattr("cadrumo.application.modelo.maritime_preview.maritime_facts_from_active_profile", lambda: facts)

    def preview(
        *, annual_salary: Decimal | None, qualifying_days: int | None, gross_navigation_income: Decimal | None
    ) -> ModeloMaritimeExemptionPreview:
        return preview_maritime_exemption_for_active_profile(
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
            operation=authority_operation,
        )

    canonical = preview(annual_salary=Decimal("36500"), qualifying_days=100, gross_navigation_income=Decimal("30000"))

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloMaritimePreviewPorts:
        assert profile_id == _PROFILE and operation is authority_operation
        return ModeloMaritimePreviewPorts(profile_id=profile_id, operation=operation, preview=preview)

    definition = build_modelo_maritime_preview_definition(factory)
    request = _request(
        ModeloMaritimePreviewRequest(
            profile_id=_PROFILE, annual_salary="36500", qualifying_days=100, gross_navigation_income="30000"
        )
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, events, operands)
            )
        )
    assert events.effects == [OperationEffect.NONE]
    result = operands.rows[0]
    assert isinstance(result, ModeloMaritimePreviewProjection)
    assert result.profile_id == _PROFILE and result.worker_class == facts.worker_class
    assert result.retmar_registered == facts.retmar_registered
    assert result.retmar_mandatory_filing == canonical.retmar_mandatory_filing
    assert tuple(row.value for row in result.observations) == tuple(
        str(row.value) for row in canonical.result.observations
    )
    assert tuple(row.legal_refs for row in result.observations) == tuple(
        row.legal_refs for row in canonical.result.observations
    )
    assert {row.casilla_id: row.value for row in result.casilla_values} == {
        key: str(value) for key, value in canonical.result.casilla_values.items()
    }
    if pathway == "retmar":
        assert not canonical.result.retmar_mandatory_filing and result.retmar_mandatory_filing
        assert result.retmar_warning is not None
        assert result.retmar_warning.code == "ERROR_RENTA_PROFILE_COMPLETENESS_WARNING"
        assert result.retmar_warning.legal_ref == "ley-35-2006:art-96"
    else:
        assert result.retmar_warning is None


def test_foreign_active_profile_refuses_before_private_fact_read(authority_operation: PinnedAuthorityOperation) -> None:
    definition = build_modelo_maritime_preview_definition(_unavailable)
    request = _request(ModeloMaritimePreviewRequest(profile_id=_PROFILE))
    events, operands = _Events(), _Operands()
    with override_settings(cadrumo_active_profile=str(uuid4())), pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, events, operands)
            )
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert not operands.rows


def test_canonical_da41_refusal_is_unchanged_and_never_publishes_result(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    events, operands = _Events(), _Operands()

    def preview(
        *, annual_salary: Decimal | None, qualifying_days: int | None, gross_navigation_income: Decimal | None
    ) -> ModeloMaritimeExemptionPreview:
        resolve_maritime_exemption(
            facts=MaritimeWorkerFacts(worker_class="trabajador_del_mar", tuna_fleet=True, pending_eu_clearance=True),
            authority=authority_operation,
        )
        pytest.fail("inactive exemption must refuse")

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloMaritimePreviewPorts:
        return ModeloMaritimePreviewPorts(profile_id=profile_id, operation=operation, preview=preview)

    definition = build_modelo_maritime_preview_definition(factory)
    request = _request(ModeloMaritimePreviewRequest(profile_id=_PROFILE))
    with (
        override_settings(cadrumo_active_profile=str(_PROFILE)),
        pytest.raises(MaritimeExemptionInactiveError) as refused,
    ):
        asyncio.run(
            definition.executor_factory.create().execute(
                request, _context(request, authority_operation, events, operands)
            )
        )
    assert refused.value.context == {"binding_id": "da41-tuna-fleet-inactive", "legal_ref": "ley-35-2006:da-41"}
    assert events.effects == [OperationEffect.NONE] and not operands.rows
