"""Registered Modelo metadata operations return their declared public results."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataProjection,
    ModeloWorkMetadataRequest,
)
from cadrumo.application.modelo.operation_definitions import (
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from cadrumo.application.modelo.work_lifecycle import get_work_unit, rename_work_unit
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.tests.modelo_operation_test_support import (
    MODELO_OPERATION_TEST_ACTOR,
    seeded_modelo_work_unit,
)

from ..adapter_composition import build_work_lifecycle_ports
from .test_registered_executor_conformance import _CloseWitness, _runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _stored_fingerprints() -> tuple[str, str]:
    objects = secure_object_repository_for_active_bucket()
    return (
        content_hash_hex(WorkUnitCatalogueRepository(objects=objects).load().model_dump(mode="json")),
        content_hash_hex(BucketEventHistoryRepository(objects=objects).load().model_dump(mode="json")),
    )


@pytest.mark.parametrize("definition_id", ["modelo.work.rename", "modelo.work.discard"])
def test_registered_metadata_operation_projects_its_actual_settled_result(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """A returned work-unit ID cannot masquerade as the declared result model."""
    with _runtime(tmp_path / definition_id, cleanup=_CloseWitness()) as (driver, registry, profile_id):
        unit = seeded_modelo_work_unit(profile_id, operation=operation)
        if definition_id == "modelo.work.rename":
            payload = ModeloWorkRenameRequest(
                work_unit_id=unit.work_unit_id,
                new_name="Approved display",
                actor=MODELO_OPERATION_TEST_ACTOR,
                observed_name=unit.name,
                observed_updated_at=unit.updated_at,
            )
            result_type = ModeloWorkRenamePublicResultV2
        else:
            payload = ModeloWorkDiscardRequest(
                baseline=ModeloWorkDiscardBaseline(
                    work_unit_id=unit.work_unit_id,
                    name=unit.name,
                    observed_updated_at=unit.updated_at,
                ),
                reason="operator discarded this work",
                actor=MODELO_OPERATION_TEST_ACTOR,
            )
            result_type = ModeloWorkDiscardPublicResultV2
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=unit.work_unit_id, payload=payload)
        )
        terminal = observed.projection
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.result_ref is not None and terminal.result_ref != unit.work_unit_id

        committed = get_work_unit(unit.work_unit_id, ports=build_work_lifecycle_ports(bucket_id=str(profile_id)))
        if definition_id == "modelo.work.rename":
            rename_work_unit(
                unit.work_unit_id,
                "A later independent rename",
                actor=MODELO_OPERATION_TEST_ACTOR,
                ports=build_work_lifecycle_ports(bucket_id=str(profile_id)),
            )

        contract = registry.lookup_public_contract(definition_id)
        assert contract.result_schema is not None
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                result_type,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert resolved.projection.work_unit_id == unit.work_unit_id
        assert resolved.projection.bucket_id == str(profile_id)
        assert resolved.projection.unit.to_work_unit() == committed
        assert contract.result_schema.schema_version == 2
        if isinstance(resolved.projection, ModeloWorkRenamePublicResultV2):
            assert resolved.projection.name == "Approved display"
        else:
            assert isinstance(resolved.projection, ModeloWorkDiscardPublicResultV2)
            assert resolved.projection.discarded is True


@pytest.mark.parametrize("definition_id", ["modelo.work.rename", "modelo.work.discard"])
def test_stale_metadata_observation_refuses_without_another_catalogue_or_event_write(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """The original observation cannot mutate a subsequently renamed unit."""
    with _runtime(tmp_path / "stale", cleanup=_CloseWitness()) as (driver, _registry, profile_id):
        observed_unit = seeded_modelo_work_unit(profile_id, operation=operation)
        rename_work_unit(
            observed_unit.work_unit_id,
            "Newer display",
            actor=MODELO_OPERATION_TEST_ACTOR,
            ports=build_work_lifecycle_ports(bucket_id=str(profile_id)),
        )
        before = _stored_fingerprints()
        payload = (
            ModeloWorkDiscardRequest(
                baseline=ModeloWorkDiscardBaseline(
                    work_unit_id=observed_unit.work_unit_id,
                    name=observed_unit.name,
                    observed_updated_at=observed_unit.updated_at,
                ),
                reason="stale approval must not take effect",
                actor=MODELO_OPERATION_TEST_ACTOR,
            )
            if definition_id == "modelo.work.discard"
            else ModeloWorkRenameRequest(
                work_unit_id=observed_unit.work_unit_id,
                new_name="Must not overwrite",
                observed_name=observed_unit.name,
                observed_updated_at=observed_unit.updated_at,
                actor=MODELO_OPERATION_TEST_ACTOR,
            )
        )
        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=observed_unit.work_unit_id, payload=payload)
        )
        after = _stored_fingerprints()

    terminal = observed.projection
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert terminal.effect is OperationEffect.NONE
    assert terminal.result_ref is None
    assert after == before


@pytest.mark.parametrize("selector", ["exact", "short", "natural"])
def test_metadata_read_uses_canonical_selection_and_persisted_period(
    tmp_path: Path, selector: str, *, operation: PinnedAuthorityOperation
) -> None:
    """All operator selectors read the same encrypted unit without writing its catalogue."""
    with _runtime(tmp_path / selector, cleanup=_CloseWitness()) as (driver, registry, profile_id):
        unit = seeded_modelo_work_unit(profile_id, operation=operation)
        payload = (
            ModeloWorkMetadataRequest(
                profile_id=UUID(str(profile_id)),
                modelo=str(unit.modelo),
                year=unit.filing_year,
                period=PublicPeriod.from_period(unit.period),
            )
            if selector == "natural"
            else ModeloWorkMetadataRequest(
                profile_id=UUID(str(profile_id)),
                work_unit_id=unit.work_unit_id if selector == "exact" else unit.work_unit_id[-12:],
            )
        )
        definition_id = MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
        contract = registry.lookup_public_contract(definition_id)
        subject_ref = profile_operation_subject(str(profile_id))
        context = OperationAccessContext(
            profile_id=UUID(str(profile_id)),
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=operation,
        )
        request = OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
        access = resolve_operation_access(registry=registry, request=request, context=context)
        assert access.request.periods == frozenset({unit.period})
        assert not access.request.period_independent
        assert contract.result_schema is not None
        assert {item.projection_id for item in access.policy.disclosures} == {contract.result_schema.schema_id}
        with pytest.raises(ProfileAccessRefusedError) as denied:
            resolve_operation_access(
                registry=registry,
                request=OperationRequest(
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    payload=payload.model_copy(update={"profile_id": uuid4()}),
                ),
                context=context,
            )
        assert denied.value.reason is AccessDenialCode.PROFILE_MISMATCH
        before = _stored_fingerprints()
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
        )
        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE
        assert _stored_fingerprints() == before
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkMetadataProjection,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert resolved.projection.profile_id == UUID(str(profile_id))
        assert resolved.projection.unit.to_work_unit() == unit
