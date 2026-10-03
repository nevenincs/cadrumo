"""Quickfile retained-pin composition and actual encrypted canonical create/refuse chain.

Disposable profile data proves local persistence behavior, not installed MCP or
live filing acceptance. No provider or credential request is sent.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from ...adapters.persistence.profile import state_projection as state_module
from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.modelo import quickfile_operation as module
from ...application.modelo.calculation_request_fields import ModeloCalculationOverride
from ...application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
from ...application.modelo.quickfile_operation import QuickfileExecutionResult
from ...application.modelo.quickfile_operation_contracts import QuickfileCalculationInputs, QuickfileRequest
from ...application.modelo.quickfile_operation_ports import QuickfileOperationPorts
from ...application.modelo.tests.m036_operation_support import PROFILE_ID, Subject
from ...application.operations.models import OperationRequest
from ...application.operations.public_period import PublicPeriod
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry import authority as authority_module
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .. import quickfile_operation_composition as composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _request(tmp_path: Path) -> OperationRequest[QuickfileRequest]:
    return OperationRequest[QuickfileRequest](
        definition_id=module.QUICKFILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=QuickfileRequest(
            profile_id=PROFILE_ID,
            modelo="130",
            period=PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
            output_path=str(tmp_path / "human-filing.txt"),
            actor="synthetic-human",
            inputs=QuickfileCalculationInputs(
                binding_overrides=(ModeloCalculationOverride(key="unknown_fixture_binding", value="1"),)
            ),
        ),
    )


def test_same_retained_pin_reaches_profile_and_workspace_without_nested_lease(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_write(_write: Callable[[], None]) -> None:
        raise AssertionError("composition and private observations cannot admit a durable write")

    def forbidden_lease() -> PinnedAuthorityOperation:
        raise AssertionError("worker observations must retain the caller's authority generation")

    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(PROFILE_ID)):
        record = register_minimal_profile(profile_id=PROFILE_ID)
        with validating_governed_facts(authority_operation):
            ports = composition.build_quickfile_operation_ports(
                profile_id=PROFILE_ID, operation=authority_operation, mutation_writer=forbidden_write
            )
            monkeypatch.setattr(authority_module, "bundled_indexed_authority", forbidden_lease)
            profile = ports.read.profile.read_profile(profile_id=str(PROFILE_ID))
            workspace = ports.read.workspace.read_workspace(bucket_id=str(PROFILE_ID))
        assert profile is not None and profile.record == record
        assert ports.operation is ports.calculation.operation is authority_operation
        assert ports.profile.profile_decode_context == authority_operation.profile_decode_context()
        assert workspace.transactions == workspace.calculation_revisions == workspace.work_units == 0


def test_bound_projection_refuses_foreign_profile_before_metadata_or_catalogue_reads(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def writer(_write: Callable[[], None]) -> None:
        raise AssertionError("private reads cannot enter a writer")

    def pointer(_profile_id: str) -> None:
        raise AssertionError("foreign-profile refusal must precede metadata lookup")

    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(PROFILE_ID)):
        register_minimal_profile(profile_id=PROFILE_ID)
        ports = composition.build_quickfile_operation_ports(
            profile_id=PROFILE_ID, operation=authority_operation, mutation_writer=writer
        )
        monkeypatch.setattr(state_module, "read_profile_bucket_by_id", pointer)
        with pytest.raises(ProfileAccessRefusedError):
            ports.read.profile.read_profile(profile_id=str(uuid4()))
        with pytest.raises(ProfileAccessRefusedError):
            ports.read.workspace.read_workspace(bucket_id=str(uuid4()))
        with pytest.raises(ProfileAccessRefusedError):
            composition.build_quickfile_operation_ports(
                profile_id=uuid4(), operation=authority_operation, mutation_writer=writer
            )


@pytest.mark.asyncio
async def test_real_canonical_create_then_input_refusal_is_partial_and_resumed_noop_is_none(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    subject = Subject(authority_operation)
    request = _request(tmp_path)
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(PROFILE_ID)):
        register_minimal_profile(profile_id=PROFILE_ID)
        for expected_effect in (OperationEffect.PARTIAL, OperationEffect.NONE):
            await module.QuickfileExecutor(composition.build_quickfile_operation_ports).execute(
                request, subject.context(module.QUICKFILE_OPERATION_DEFINITION_ID)
            )
            projection = cast(QuickfileExecutionResult, subject.operands.values[-1]).projection
            assert projection.stopped_at_stage is QuickfileStage.CALCULATE and not projection.completed
            assert projection.work_unit_id is not None
            assert projection.stages[2].error is not None
            assert all(row.status is QuickfileStageStatus.SKIPPED for row in projection.stages[3:])
            assert projection.effect is subject.events.effects[-1] is expected_effect
            assert (projection.write_count > 0) is (expected_effect is OperationEffect.PARTIAL)
            assert not Path(request.payload.output_path).exists()
        assert projection.stages[1].message == "resumed"


@pytest.mark.asyncio
async def test_revocation_after_actual_create_remains_authoritative_and_thread_is_joined(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    subject = Subject(authority_operation)
    request = _request(tmp_path)
    completed: list[bool] = []

    def factory(
        *, profile_id: UUID, operation: PinnedAuthorityOperation, mutation_writer: Callable[[Callable[[], None]], None]
    ) -> QuickfileOperationPorts:
        def admitted(write: Callable[[], None]) -> None:
            mutation_writer(write)
            completed.append(True)
            subject.fence.deny = True

        return composition.build_quickfile_operation_ports(
            profile_id=profile_id, operation=operation, mutation_writer=admitted
        )

    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(PROFILE_ID)):
        register_minimal_profile(profile_id=PROFILE_ID)
        with pytest.raises(ProfileAccessRefusedError):
            await module.QuickfileExecutor(factory).execute(
                request, subject.context(module.QUICKFILE_OPERATION_DEFINITION_ID)
            )
        assert completed and not subject.operands.values
        assert subject.events.effects[-1] is OperationEffect.PARTIAL
        assert not Path(request.payload.output_path).exists()
