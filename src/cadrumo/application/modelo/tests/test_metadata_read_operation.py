"""Work metadata reads are admitted for external client under the same selection and scope rules as the other frontends."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationRegistry
from ..metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataRequest,
    build_modelo_metadata_definition,
    build_modelo_metadata_registration,
)
from ..work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .work_operation_support import FIRST_QUARTER_PERIOD, first_quarter_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PERIOD = FIRST_QUARTER_PERIOD


def test_metadata_read_is_admitted_on_the_external_client_frontend_without_a_commit_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = first_quarter_unit(_PROFILE)

    class Repository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    def factory() -> SimpleNamespace:
        return SimpleNamespace(work_unit_repository=Repository())

    typed_factory = cast(ActiveWorkLifecyclePortsFactory, cast(object, factory))
    definition = build_modelo_metadata_definition(typed_factory)
    registration = build_modelo_metadata_registration(definition, typed_factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    resolved = resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=ModeloWorkMetadataRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id),
        ),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )
    assert resolved.request.frontend is OperationFrontendProjection.EXTERNAL_CLIENT
    assert resolved.request.periods == frozenset({_PERIOD})
    assert AccessAction.COMMIT not in resolved.policy.actions
