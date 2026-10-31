"""Registered profile edits keep the snapshot the operator actually reviewed."""

from __future__ import annotations

import asyncio
import logging
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
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.logging import get_logger
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .....tests.log_records import delivered_records
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
        authenticate_profile_for_invocation(
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


_SCALAR_EDIT_VALUES = {"stale": "ca", "first": "en", "fresh": "ca", "wrong_digest": "hu", "wrong_revision": "hu"}
_ROW_EDIT_VALUES = {
    "stale": "Stale activity",
    "first": "First activity",
    "fresh": "Fresh activity",
    "wrong_digest": "Wrong digest activity",
    "wrong_revision": "Wrong revision activity",
}


def _edit_request(request_kind: str, profile: UUID, *, revision: int, digest: str, value: str) -> OperationRequest[Any]:
    if request_kind == "field":
        return _field_request(profile, revision=revision, digest=digest, value=value)
    if request_kind == "patch":
        return OperationRequest(
            definition_id=PROFILE_PATCH_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile}",
            payload=ProfilePatchOperationRequest(
                profile_id=profile,
                expected_revision=revision,
                expected_content_digest=digest,
                values=(ProfilePatchValue(question_id="output-language", value=value),),
            ),
        )
    return _row_request(profile, revision=revision, digest=digest, value=value)


async def _submit_and_settle(supervisor: OperationSupervisor, request: OperationRequest[Any], operation_id: str):
    submitted = await supervisor.submit(request, operation_id=operation_id)
    return await run_to_settlement(supervisor, submitted)


def _assert_edit_applied(terminal) -> None:
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED


def _assert_edit_conflict_refused(terminal) -> None:
    assert terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.failure_error_code == "FAIL_PROFILE_RECORD_CONFLICT"
    assert terminal.effect is OperationEffect.NONE


def _assert_conflict_diagnostic_omits_digests(
    caplog: pytest.LogCaptureFixture, stale_intent: OperationRequest[Any], initial: Any, after_first: Any
) -> None:
    diagnostics = [
        record.getMessage()
        for record in delivered_records(caplog)
        if record.name.endswith("user_profile.profile_operation_execution")
    ]
    assert diagnostics == [
        f"profile edit conflict operation={'b' * 64} definition={stale_intent.definition_id} "
        f"fields={(PROFILE_OUTPUT_LANGUAGE_PATH,)} "
        f"expected_revision={initial.record_revision} current_revision={after_first.record_revision} "
        "digest_matches=False"
    ]
    assert initial.content_digest not in diagnostics[0]
    assert after_first.content_digest not in diagnostics[0]


def _assert_surviving_edits(request_kind: str, final: Any) -> None:
    values = record_to_path_values(final)
    if request_kind != "row":
        assert values[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
    else:
        assert values["activities.0.description"] == "First activity"
        assert values["activities.1.description"] == "Fresh activity"
        assert "Stale activity" not in values.values()


@pytest.mark.parametrize("request_kind", ["field", "row", "patch"])
def test_separately_submitted_edits_cannot_overwrite_a_changed_profile(
    tmp_path: Path, request_kind: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = _ROW_EDIT_VALUES if request_kind == "row" else _SCALAR_EDIT_VALUES
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with bundled_indexed_authority().operation() as authority:
            repository = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            )
            initial = repository.load(profile_id)

            def build_request(label: str, *, revision: int, digest: str) -> OperationRequest[Any]:
                return _edit_request(request_kind, profile_id, revision=revision, digest=digest, value=values[label])

            with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
                assert isinstance(objects, SecureObjectRepository)
                supervisor = _supervisor(root, objects=objects, authority=authority)
                # CLI tests configure the root logger. Capture this owner's
                # diagnostics independently of that process-global setup.
                logger = get_logger("cadrumo.application.user_profile.profile_operation_execution")
                caplog.set_level(logging.WARNING, logger=logger.name)
                monkeypatch.setattr(logger, "handlers", [caplog.handler])
                monkeypatch.setattr(logger, "propagate", False)

                async def _exercise() -> None:
                    stale_intent = build_request(
                        "stale", revision=initial.record_revision, digest=initial.content_digest
                    )
                    first_request = build_request(
                        "first", revision=initial.record_revision, digest=initial.content_digest
                    )
                    _assert_edit_applied(await _submit_and_settle(supervisor, first_request, "a" * 64))
                    after_first = repository.load(profile_id)
                    assert after_first.record_revision > initial.record_revision
                    # The subject lease serializes submission; retain the second operator's
                    # earlier intent and submit it after the first publication.
                    _assert_edit_conflict_refused(await _submit_and_settle(supervisor, stale_intent, "b" * 64))
                    assert repository.load(profile_id).content_digest == after_first.content_digest
                    if request_kind != "row":
                        _assert_conflict_diagnostic_omits_digests(caplog, stale_intent, initial, after_first)

                    fresh_request = build_request(
                        "fresh", revision=after_first.record_revision, digest=after_first.content_digest
                    )
                    _assert_edit_applied(await _submit_and_settle(supervisor, fresh_request, "c" * 64))
                    after_fresh = repository.load(profile_id)
                    assert after_fresh.record_revision > after_first.record_revision

                    wrong_digest = build_request("wrong_digest", revision=after_fresh.record_revision, digest="0" * 64)
                    _assert_edit_conflict_refused(await _submit_and_settle(supervisor, wrong_digest, "d" * 64))
                    wrong_revision = build_request(
                        "wrong_revision", revision=initial.record_revision, digest=after_fresh.content_digest
                    )
                    _assert_edit_conflict_refused(await _submit_and_settle(supervisor, wrong_revision, "e" * 64))
                    final = repository.load(profile_id)
                    assert final.record_revision == after_fresh.record_revision
                    assert final.content_digest == after_fresh.content_digest
                    _assert_surviving_edits(request_kind, final)

                asyncio.run(_exercise())
