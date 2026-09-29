"""The registered revision read binds selected metadata to its original profile."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.verification_report import VerificationReportCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import work_addressing
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..revision_selection_operation import (
    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionExecutor,
    ModeloWorkRevisionProjection,
    ModeloWorkRevisionRequest,
    build_modelo_work_revision_definition,
    build_modelo_work_revision_registration,
)
from ..verification_repository_ports import VerificationRepositoryBundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_REVISION_ID = "a" * 64
_REPORT_ID = "b" * 64


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=period, revision_id="test-revision"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="test-revision",
        name="First-quarter return",
        created_at=instant,
        updated_at=instant,
        state=WorkUnitState.BORRADOR,
        current_calculation_revision_id=_REVISION_ID,
    )


def _projection() -> ModeloWorkRevisionProjection:
    return ModeloWorkRevisionProjection(
        profile_id=_PROFILE,
        unit=ModeloWorkMetadataSnapshot.from_work_unit(_unit()),
        calculation_revision_id=_REVISION_ID,
        calculation_state=CalculationRevisionState.VERIFICADO_COMPLETO,
        verification_report_id=_REPORT_ID,
        granted_verificado_completo=True,
    )


def test_registered_projection_roundtrips_without_financial_values_or_report_contents() -> None:
    definition = build_modelo_work_revision_definition(_unavailable_bundle)
    registration = build_modelo_work_revision_registration(definition, _unavailable_bundle)
    OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    projection = _projection()
    restored = ModeloWorkRevisionProjection.model_validate_json(projection.model_dump_json())

    assert restored == projection
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "modelo.work.revision.result"
    encoded = projection.model_dump_json()
    assert _REVISION_ID in encoded and _REPORT_ID in encoded
    assert "casillas" not in encoded and "findings" not in encoded and "tax_id" not in encoded


@pytest.mark.parametrize(
    "alteration",
    [
        {"profile_id": str(_OTHER_PROFILE)},
        {"verification_report_id": None},
        {"granted_verificado_completo": False},
        {"result_version": 2},
    ],
)
def test_projection_refuses_substituted_profile_or_report_grant(alteration: dict[str, object]) -> None:
    payload = _projection().model_dump(mode="json") | alteration
    with pytest.raises(ValidationError):
        ModeloWorkRevisionProjection.model_validate_json(json.dumps(payload))


def test_historical_result_uses_encrypted_admission_period_without_reresolving_changed_catalogue() -> None:
    definition = build_modelo_work_revision_definition(_unavailable_bundle)
    registration = build_modelo_work_revision_registration(definition, _unavailable_bundle)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloWorkRevisionRequest(profile_id=_PROFILE, calculation_revision_id=_REVISION_ID),
    )
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({_unit().period}),
        period_independent=False,
        destination_id=uuid4(),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=admitted.destination_id,
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )

    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.request.periods == admitted.periods
    assert next(iter(resolved.policy.disclosures)).projection_id == "modelo.work.revision.result"

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=_OTHER_PROFILE,
                destination_id=admitted.destination_id,
                action=AccessAction.RESULT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
                admitted_request=admitted,
            ),
        )
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize("positional_work_id", [False, True])
def test_fresh_submission_derives_period_from_selected_persisted_unit(
    positional_work_id: bool, *, authority_operation: PinnedAuthorityOperation
) -> None:
    unit = _unit()
    calculation_loads: list[PinnedAuthorityOperation | None] = []

    class WorkRepository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    class CalculationRepository:
        bucket_id = str(_PROFILE)

        def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
            calculation_loads.append(operation)
            return CalculationRevisionCatalogue()

    def bundle(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE)
        assert operation is authority_operation
        return cast(
            VerificationRepositoryBundle,
            cast(object, SimpleNamespace(work_unit=WorkRepository(), calculation=CalculationRepository())),
        )

    definition = build_modelo_work_revision_definition(bundle)
    registration = build_modelo_work_revision_registration(definition, bundle)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=(
            ModeloWorkRevisionRequest(
                profile_id=_PROFILE,
                calculation_revision_id=unit.work_unit_id,
                default_for="verify",
            )
            if positional_work_id
            else ModeloWorkRevisionRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id)
        ),
    )
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )

    assert resolved.request.periods == frozenset({unit.period})
    assert not resolved.request.period_independent
    assert calculation_loads == ([authority_operation] if positional_work_id else [])


def test_fresh_submission_without_authority_pin_refuses_before_repository_creation() -> None:
    bundle_calls = 0

    def bundle(_profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        nonlocal bundle_calls
        bundle_calls += 1
        raise AssertionError("a live revision resolution must be pinned before private repository access")

    definition = build_modelo_work_revision_definition(bundle)
    registration = build_modelo_work_revision_registration(definition, bundle)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloWorkRevisionRequest(profile_id=_PROFILE, work_unit_id=_unit().work_unit_id),
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
            ),
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert bundle_calls == 0


@pytest.mark.parametrize("selector", ["exact", "natural"])
def test_revision_capture_passes_one_authority_pin_through_every_catalogue_read(
    selector: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2026, "1T")
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE),
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id="2026-y-siguientes",
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="First-quarter return",
        created_at=datetime(2026, 3, 10, 12, tzinfo=UTC),
        updated_at=datetime(2026, 3, 10, 12, tzinfo=UTC),
        state=WorkUnitState.BORRADOR,
        current_calculation_revision_id=_REVISION_ID,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    unit = WorkUnit.model_validate(unit.model_dump(mode="python") | {"current_calculation_revision_id": revision_id})
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=str(unit.modelo),
            revision_id=unit.revision_id,
            modelo_year=unit.filing_year,
            period=unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calculation_loads: list[PinnedAuthorityOperation | None] = []

    class WorkRepository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    class CalculationRepository:
        bucket_id = str(_PROFILE)

        def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
            calculation_loads.append(operation)
            assert operation is authority_operation
            return CalculationRevisionCatalogue(revisions={revision_id: revision})

    class VerificationRepository:
        bucket_id = str(_PROFILE)

        def load(self, *, operation: PinnedAuthorityOperation | None = None) -> VerificationReportCatalogue:
            assert operation is authority_operation
            return VerificationReportCatalogue()

    bundle = cast(
        VerificationRepositoryBundle,
        cast(
            object,
            SimpleNamespace(
                work_unit=WorkRepository(),
                calculation=CalculationRepository(),
                verification=VerificationRepository(),
            ),
        ),
    )

    def unexpected_lease() -> object:
        pytest.fail("revision capture opened an ambient authority lease instead of using its executor pin")

    monkeypatch.setattr(work_addressing, "bundled_indexed_authority", unexpected_lease)

    subject_ref = profile_operation_subject(str(_PROFILE))
    payload = (
        ModeloWorkRevisionRequest(profile_id=_PROFILE, calculation_revision_id=revision_id)
        if selector == "exact"
        else ModeloWorkRevisionRequest(
            profile_id=_PROFILE,
            modelo=str(unit.modelo),
            year=unit.filing_year,
            period=PublicPeriod.from_period(unit.period),
        )
    )
    request = OperationRequest[ModeloWorkRevisionRequest](
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=payload,
    )

    class Events:
        def __init__(self) -> None:
            self.phases: list[object] = []
            self.effects: list[OperationEffect] = []

        async def phase(self, phase_code: object) -> None:
            self.phases.append(phase_code)

        async def effect(self, effect: OperationEffect) -> None:
            self.effects.append(effect)

    class Operands:
        def __init__(self) -> None:
            self.value: BaseModel | None = None

        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            del written_at
            self.value = operand
            return _REPORT_ID

    events = Events()
    operands = Operands()
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                authority_operation=authority_operation,
                identity=SimpleNamespace(subject_ref=subject_ref),
                events=events,
                operands=operands,
            ),
        ),
    )

    result_ref = asyncio.run(
        ModeloWorkRevisionExecutor(lambda _profile_id, *, operation: bundle).execute(request, context)
    )

    assert result_ref == _REPORT_ID
    assert isinstance(operands.value, ModeloWorkRevisionProjection)
    assert operands.value.calculation_revision_id == revision_id
    assert calculation_loads == [authority_operation] * (3 if selector == "exact" else 2)
    assert events.phases == [MODELO_WORK_REVISION_OPERATION_DEFINITION_ID]
    assert events.effects == [OperationEffect.NONE]


def _unavailable_bundle(_profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
    raise AssertionError("historical result access must not reopen private repositories")
