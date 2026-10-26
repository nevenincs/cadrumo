"""Registered profile row changes and setup completion use canonical CAS writers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.custody_ports import profile_custody_secure_object_repository
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
    ProfileCompleteSetupOperationRequest,
    ProfileCompleteSetupOperationResult,
    ProfileRepeatableRowChangeOperationResult,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    ProfileRepeatableRowValue,
    project_profile_mutation_result,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.section_rows import add_profile_repeatable_section_row
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState

from .supervision_support import run_to_settlement

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "profile-additional-operation-passphrase"  # noqa: S105 - isolated test credential


def _profile() -> UUID:
    with bundled_indexed_authority().operation() as authority:
        created = register_profile_with_credentials(
            label="Additional profile operations",
            passphrase=_PASSWORD,
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=created.profile_id,
            passphrase_callback=lambda: _PASSWORD,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(created.profile_id)


def _supervisor(
    root: Path, objects: SecureObjectRepository, authority: PinnedAuthorityOperation
) -> tuple[OperationSupervisor, OperationSecureReferenceRepository]:
    journal = OperationJournalRepository(storage_root=root)
    operands = operation_secure_reference_repository(objects=objects)
    supervisor = OperationSupervisor(
        authority_operation=authority,
        registry=OperationRegistry(
            definitions=USER_PROFILE_OPERATION_DEFINITIONS,
            public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operands,
        owner_id="a" * 64,
        lease_token_factory=lambda: "b" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=6),
    )
    return supervisor, operands


def _current(profile_id: UUID, authority: PinnedAuthorityOperation):
    return ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=authority.profile_decode_context()
    ).load(profile_id)


async def _settle[PayloadT: BaseModel](
    supervisor: OperationSupervisor, request: OperationRequest[PayloadT], operation_id: str
) -> OperationPersistedSnapshot:
    created = await supervisor.submit(request, operation_id=operation_id)
    return await run_to_settlement(supervisor, created)


def test_registered_row_update_and_remove_publish_exact_row_and_safe_projection(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _profile()
        with bundled_indexed_authority().operation() as authority:
            baseline = _current(profile_id, authority)
            added = add_profile_repeatable_section_row(
                profile_id=str(profile_id),
                section_key="activities",
                values={"description": "Before"},
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
                schema=authority.profile_schema(),
                profile_decode_context=authority.profile_decode_context(),
            )
            row_key = str(added.row_index)
            with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
                assert isinstance(objects, SecureObjectRepository)
                supervisor, operands = _supervisor(root, objects, authority)
                updated = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileRepeatableRowUpdateOperationRequest(
                                profile_id=profile_id,
                                expected_revision=added.record.record_revision,
                                expected_content_digest=added.record.content_digest,
                                section_key="activities",
                                row_key=row_key,
                                values=(ProfileRepeatableRowValue(field_key="description", value="After"),),
                            ),
                        ),
                        "1" * 64,
                    )
                )
                assert updated.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert updated.effect is OperationEffect.UPDATED
                assert updated.terminal_receipt is not None
                assert updated.terminal_receipt.result_ref is not None
                result = asyncio.run(
                    operands.resolve(updated.terminal_receipt.result_ref, ProfileRepeatableRowChangeOperationResult)
                )
                assert result.row_key == row_key and result.changed
                assert (
                    record_to_path_values(_current(profile_id, authority))[f"activities.{row_key}.description"]
                    == "After"
                )
                projection = project_profile_mutation_result(result, updated.terminal_receipt)
                assert projection.model_dump() == {
                    "profile_id": profile_id,
                    "record_revision": result.record_revision,
                    "section_key": "activities",
                    "row_key": row_key,
                    "changed": True,
                }
                stale_remove = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileRepeatableRowRemoveOperationRequest(
                                profile_id=profile_id,
                                expected_revision=added.record.record_revision,
                                expected_content_digest=added.record.content_digest,
                                section_key="activities",
                                row_key=row_key,
                            ),
                        ),
                        "5" * 64,
                    )
                )
                assert stale_remove.terminal_condition is OperationTerminalCondition.FAILED
                assert stale_remove.terminal_receipt is not None
                assert stale_remove.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
                assert (
                    record_to_path_values(_current(profile_id, authority))[f"activities.{row_key}.description"]
                    == "After"
                )
                removed = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileRepeatableRowRemoveOperationRequest(
                                profile_id=profile_id,
                                expected_revision=result.record_revision,
                                expected_content_digest=result.content_digest,
                                section_key="activities",
                                row_key=row_key,
                            ),
                        ),
                        "2" * 64,
                    )
                )
                assert removed.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert removed.effect is OperationEffect.UPDATED
                assert f"activities.{row_key}.description" not in record_to_path_values(_current(profile_id, authority))


def test_registered_complete_setup_requires_current_baseline_and_reports_noop(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _profile()
        with bundled_indexed_authority().operation() as authority:
            facts = complete_profile_facts(authority.profile_schema())
            populated = upsert_test_profile_facts(profile_id, facts, root=root)
            assert populated.setup_state is ProfileSetupState.INCOMPLETE
            with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
                assert isinstance(objects, SecureObjectRepository)
                supervisor, operands = _supervisor(root, objects, authority)
                first = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileCompleteSetupOperationRequest(
                                profile_id=profile_id,
                                expected_revision=populated.record_revision,
                                expected_content_digest=populated.content_digest,
                            ),
                        ),
                        "3" * 64,
                    )
                )
                assert first.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert first.effect is OperationEffect.UPDATED
                assert first.terminal_receipt is not None
                assert first.terminal_receipt.result_ref is not None
                result = asyncio.run(
                    operands.resolve(first.terminal_receipt.result_ref, ProfileCompleteSetupOperationResult)
                )
                assert not result.already_complete
                assert _current(profile_id, authority).setup_state is ProfileSetupState.COMPLETE
                stale_completion = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileCompleteSetupOperationRequest(
                                profile_id=profile_id,
                                expected_revision=populated.record_revision,
                                expected_content_digest=populated.content_digest,
                            ),
                        ),
                        "6" * 64,
                    )
                )
                assert stale_completion.terminal_condition is OperationTerminalCondition.FAILED
                assert stale_completion.terminal_receipt is not None
                assert stale_completion.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
                assert _current(profile_id, authority).content_digest == result.content_digest
                repeated = asyncio.run(
                    _settle(
                        supervisor,
                        OperationRequest(
                            definition_id=PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
                            subject_ref=f"profile:{profile_id}",
                            payload=ProfileCompleteSetupOperationRequest(
                                profile_id=profile_id,
                                expected_revision=result.record_revision,
                                expected_content_digest=result.content_digest,
                            ),
                        ),
                        "4" * 64,
                    )
                )
                assert repeated.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert repeated.effect is OperationEffect.NONE
                assert repeated.terminal_receipt is not None
                assert repeated.terminal_receipt.result_ref is not None
                unchanged = asyncio.run(
                    operands.resolve(repeated.terminal_receipt.result_ref, ProfileCompleteSetupOperationResult)
                )
                assert unchanged.already_complete
                assert unchanged.record_revision == result.record_revision
