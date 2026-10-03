"""Registered profile edits keep the snapshot the operator actually reviewed."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.custody_ports import profile_custody_secure_object_repository
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .supervision_support import run_to_settlement

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_PROFILE_CREDENTIAL = "registered-profile-cas-test-passphrase"


def _register_profile() -> UUID:
    with bundled_indexed_authority().operation() as authority:
        registered = register_profile_with_credentials(
            label="Registered profile CAS",
            passphrase=_PROFILE_CREDENTIAL,
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        login_profile(
            name=registered.profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(registered.profile_id)


def _supervisor(
    root: Path, *, objects: SecureObjectRepository, authority: PinnedAuthorityOperation
) -> OperationSupervisor:
    journal = OperationJournalRepository(storage_root=root)
    return OperationSupervisor(
        authority_operation=authority,
        registry=OperationRegistry(
            definitions=USER_PROFILE_OPERATION_DEFINITIONS,
            public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(objects=objects),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=6),
    )


def _field_request(
    profile_id: UUID, *, revision: int, digest: str, value: str
) -> OperationRequest[ProfileFieldMutationOperationRequest]:
    return OperationRequest(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        payload=ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value=value,
        ),
    )


def _row_request(
    profile_id: UUID, *, revision: int, digest: str, value: str
) -> OperationRequest[ProfileRepeatableRowMutationOperationRequest]:
    return OperationRequest(
        definition_id=PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        payload=ProfileRepeatableRowMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            section_key="activities",
            values=(ProfileRepeatableRowValue(field_key="description", value=value),),
        ),
    )


@pytest.mark.parametrize("request_kind", ["field", "row"])
def test_separately_submitted_edits_cannot_overwrite_a_changed_profile(tmp_path: Path, request_kind: str) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with bundled_indexed_authority().operation() as authority:
            repository = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            )
            initial = repository.load(profile_id)

            def build_request(profile: UUID, *, revision: int, digest: str, value: str) -> OperationRequest[Any]:
                if request_kind == "field":
                    return _field_request(profile, revision=revision, digest=digest, value=value)
                return _row_request(profile, revision=revision, digest=digest, value=value)

            with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
                assert isinstance(objects, SecureObjectRepository)
                supervisor = _supervisor(root, objects=objects, authority=authority)

                async def _exercise() -> None:
                    stale_intent = build_request(
                        profile_id,
                        revision=initial.record_revision,
                        digest=initial.content_digest,
                        value="ca" if request_kind == "field" else "Stale activity",
                    )
                    first = await supervisor.submit(
                        build_request(
                            profile_id,
                            revision=initial.record_revision,
                            digest=initial.content_digest,
                            value="en" if request_kind == "field" else "First activity",
                        ),
                        operation_id="a" * 64,
                    )
                    first_terminal = await run_to_settlement(supervisor, first)
                    assert first_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert first_terminal.effect is OperationEffect.UPDATED
                    after_first = repository.load(profile_id)
                    assert after_first.record_revision > initial.record_revision
                    # The subject lease serializes submission; retain the second operator's
                    # earlier intent and submit it after the first publication.
                    stale = await supervisor.submit(stale_intent, operation_id="b" * 64)
                    stale_terminal = await run_to_settlement(supervisor, stale)
                    assert stale_terminal.terminal_condition is OperationTerminalCondition.FAILED
                    assert stale_terminal.terminal_receipt is not None
                    assert stale_terminal.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
                    assert stale_terminal.effect is not OperationEffect.UPDATED
                    assert repository.load(profile_id).content_digest == after_first.content_digest

                    fresh = await supervisor.submit(
                        build_request(
                            profile_id,
                            revision=after_first.record_revision,
                            digest=after_first.content_digest,
                            value="ca" if request_kind == "field" else "Fresh activity",
                        ),
                        operation_id="c" * 64,
                    )
                    fresh_terminal = await run_to_settlement(supervisor, fresh)
                    assert fresh_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert fresh_terminal.effect is OperationEffect.UPDATED
                    after_fresh = repository.load(profile_id)
                    assert after_fresh.record_revision > after_first.record_revision

                    wrong_digest = await supervisor.submit(
                        build_request(
                            profile_id,
                            revision=after_fresh.record_revision,
                            digest="0" * 64,
                            value="hu" if request_kind == "field" else "Wrong digest activity",
                        ),
                        operation_id="d" * 64,
                    )
                    wrong_digest_terminal = await run_to_settlement(supervisor, wrong_digest)
                    assert wrong_digest_terminal.terminal_condition is OperationTerminalCondition.FAILED
                    assert wrong_digest_terminal.terminal_receipt is not None
                    assert wrong_digest_terminal.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
                    wrong_revision = await supervisor.submit(
                        build_request(
                            profile_id,
                            revision=initial.record_revision,
                            digest=after_fresh.content_digest,
                            value="hu" if request_kind == "field" else "Wrong revision activity",
                        ),
                        operation_id="e" * 64,
                    )
                    wrong_revision_terminal = await run_to_settlement(supervisor, wrong_revision)
                    assert wrong_revision_terminal.terminal_condition is OperationTerminalCondition.FAILED
                    assert wrong_revision_terminal.terminal_receipt is not None
                    assert wrong_revision_terminal.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
                    final = repository.load(profile_id)
                    assert final.record_revision == after_fresh.record_revision
                    assert final.content_digest == after_fresh.content_digest
                    values = record_to_path_values(final)
                    if request_kind == "field":
                        assert values[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
                    else:
                        assert values["activities.0.description"] == "First activity"
                        assert values["activities.1.description"] == "Fresh activity"
                        assert "Stale activity" not in values.values()

                asyncio.run(_exercise())
