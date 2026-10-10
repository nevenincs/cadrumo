"""The revision snapshot read is admitted for MCP under the same persisted-revision scope as the other frontends."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, Availability
from ..revision_operation_access import compose_modelo_revision_access
from ..revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotRequest,
    build_modelo_work_revision_snapshot_definition,
    build_modelo_work_revision_snapshot_registration,
)
from ..verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PERIOD = Period.from_year_and_code(2026, "1T")
_REVISION_ID = "a" * 64


def _unit() -> WorkUnit:
    instant = datetime(2026, 3, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=_PERIOD, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="2026-y-siguientes",
        name="First quarter",
        created_at=instant,
        updated_at=instant,
    )


def test_revision_snapshot_is_admitted_on_the_mcp_frontend_without_a_commit_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _unit()

    class Catalogue:
        def get(self, revision_id: str) -> SimpleNamespace | None:
            return SimpleNamespace(work_unit_id=unit.work_unit_id) if revision_id == _REVISION_ID else None

    class Calculations:
        bucket_id = str(_PROFILE)

        def load(self, *, operation: PinnedAuthorityOperation) -> Catalogue:
            assert operation is authority_operation
            return Catalogue()

    class WorkUnits:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE) and operation is authority_operation
        return cast(
            VerificationRepositoryBundle,
            cast(object, SimpleNamespace(calculation=Calculations(), work_unit=WorkUnits())),
        )

    typed_factory = cast(VerificationRepositoryBundleFactory, factory)
    definition = build_modelo_work_revision_snapshot_definition(typed_factory)
    registration = build_modelo_work_revision_snapshot_registration(
        definition, access_resolver=compose_modelo_revision_access(typed_factory)
    )
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
            subject_ref=unit.work_unit_id,
            payload=ModeloWorkRevisionSnapshotRequest(profile_id=_PROFILE, calculation_revision_id=_REVISION_ID),
        ),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.MCP,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )

    assert OperationFrontendProjection.MCP in definition.permitted_frontends
    assert OperationFrontendProjection.MCP in registration.contract.permitted_frontends
    assert resolved.request.frontend is OperationFrontendProjection.MCP
    assert resolved.request.periods == frozenset({_PERIOD})
    assert AccessAction.COMMIT not in resolved.policy.actions
