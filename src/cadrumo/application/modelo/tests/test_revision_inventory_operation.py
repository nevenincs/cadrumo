"""Revision discovery is admitted for MCP under the same scope rules as the other frontends."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, Availability
from ..revision_inventory_operation import (
    MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionsRequest,
    build_modelo_work_revisions_definition,
    build_modelo_work_revisions_registration,
)
from ..verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PERIOD = Period.from_year_and_code(2026, "1T")


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


def _registry(unit: WorkUnit, authority_operation: PinnedAuthorityOperation):
    class Repository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    def factory(profile_id: str, *, operation: PinnedAuthorityOperation) -> VerificationRepositoryBundle:
        assert profile_id == str(_PROFILE) and operation is authority_operation
        return cast(VerificationRepositoryBundle, cast(object, SimpleNamespace(work_unit=Repository())))

    typed_factory = cast(VerificationRepositoryBundleFactory, factory)
    definition = build_modelo_work_revisions_definition(typed_factory)
    registration = build_modelo_work_revisions_registration(definition, typed_factory)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(work_unit_id: str | None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloWorkRevisionsRequest(profile_id=_PROFILE, work_unit_id=work_unit_id),
    )


def _context(
    registration, authority_operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )


def test_revision_discovery_is_admitted_on_the_mcp_frontend_without_a_commit_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _unit()
    registry, registration = _registry(unit, authority_operation)
    definition = registry.lookup(MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID)
    assert OperationFrontendProjection.MCP in definition.permitted_frontends
    assert OperationFrontendProjection.MCP in registration.contract.permitted_frontends

    whole_profile = resolve_operation_access(
        registry=registry,
        request=_request(None),
        context=_context(registration, authority_operation, OperationFrontendProjection.MCP),
    )
    one_unit = resolve_operation_access(
        registry=registry,
        request=_request(unit.work_unit_id),
        context=_context(registration, authority_operation, OperationFrontendProjection.MCP),
    )

    assert whole_profile.request.frontend is OperationFrontendProjection.MCP
    assert whole_profile.request.profile_id == _PROFILE
    assert whole_profile.request.period_independent and whole_profile.policy.requires_all_periods
    assert one_unit.request.frontend is OperationFrontendProjection.MCP
    assert one_unit.request.periods == frozenset({_PERIOD})
    assert AccessAction.COMMIT not in whole_profile.policy.actions
    assert AccessAction.COMMIT not in one_unit.policy.actions
