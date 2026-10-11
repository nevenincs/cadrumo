"""Recovery revocation through the real supervisor, its real resolver and real profile custody."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ...application.operations.access_resolution import (
    SINGLE_RUN_COMMITTING_ACTIONS,
    OperationAccessContext,
    resolve_operation_access,
)
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.recovery_custody import (
    ProfileRecoveryError,
    enroll_profile_recovery,
    profile_recovery_status,
)
from ...application.user_profile.recovery_revoke_operation import (
    RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
    RecoveryRevokeProjection,
    RecoveryRevokeRequest,
    recovery_revoke_operation,
)
from ...core.config import override_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .command_line_rendering import Printed, assert_prints, command_result, json_document
from .profile_operation_supervisor import (
    PROFILE_INPUT,
    SettledOperation,
    SupervisedProfile,
    supervised_profile,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_WRONG_INPUT = "not-the-passphrase-of-this-profile"


def _enroll(profile: SupervisedProfile) -> None:
    """Enrol recovery through the real door, discarding the code these cases do not need."""
    enroll_profile_recovery(
        profile_id=profile.profile_id,
        current_passphrase=PROFILE_INPUT,
        recovery_handover=lambda enrollment: enrollment.recovery_key.code,
        root=profile.root,
    )


def _revoke(profile: SupervisedProfile, passphrase: bytearray) -> SettledOperation:
    return profile.run(
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile.profile_id)),
        payload=RecoveryRevokeRequest(profile_id=profile.profile_id),
        secret=passphrase,
    )


def _enrolled(profile: SupervisedProfile) -> bool:
    return profile_recovery_status(profile_id=profile.profile_id, root=profile.root).enrolled


def _disable(*, reveal_identifiers: bool) -> dict[str, object]:
    """Run ``config profile recovery disable`` and return the result it printed."""
    return command_result(
        "config",
        "profile",
        "recovery",
        "disable",
        "--secrets-stdin",
        stdin=json.dumps({"passphrase": PROFILE_INPUT}),
        reveal_identifiers=reveal_identifiers,
    )


def _stored_bytes(root: Path) -> bytes:
    return b"".join(path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file())


def test_revocation_proves_the_passphrase_removes_the_wrapper_and_prints_what_the_command_prints(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    with (
        supervised_profile(tmp_path, (recovery_revoke_operation(),)) as profile,
        override_settings(cadrumo_active_profile=str(profile.profile_id), cadrumo_output_language="en"),
    ):
        _enroll(profile)
        refused = _revoke(profile, bytearray(_WRONG_INPUT, "utf-8"))
        kept = _enrolled(profile)
        refusal = profile.error_detail(refused)

        # The command removes the enrolment each time it runs, so it is enrolled again before the
        # next run, and before the operation is asked for the same work on the same storage.
        removed_by_default = _disable(reveal_identifiers=False)
        printed_again = Printed(default=_disable(reveal_identifiers=False), revealed=_disable(reveal_identifiers=True))
        _enroll(profile)
        printed = Printed(default=removed_by_default, revealed=_disable(reveal_identifiers=True))

        _enroll(profile)
        passphrase = bytearray(PROFILE_INPUT, "utf-8")
        revoked = _revoke(profile, passphrase)
        removed = not _enrolled(profile)
        result = profile.result(revoked, RecoveryRevokeProjection)
        again = _revoke(profile, bytearray(PROFILE_INPUT, "utf-8"))
        unchanged = profile.result(again, RecoveryRevokeProjection)
        # The session this process holds was bound before the revocation and still reads the record.
        record = ProfileRecordRepository.for_current_session(
            profile.profile_id, profile_decode_context=profile.decode_context
        ).load(profile.profile_id)
        stored = _stored_bytes(profile.root)

    assert refused.receipt.condition is OperationTerminalCondition.REFUSED
    assert refused.receipt.effect is OperationEffect.NONE
    assert kept
    assert refusal.error_code == get_registered_error_code(ProfileRecoveryError).code
    assert refusal.message_key == "application.user_profile.errors.passphrase_current_rejected"
    assert refusal.context == ()
    assert (revoked.receipt.condition, revoked.receipt.effect) == (
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.UPDATED,
    )
    assert removed
    assert (result.enrolled, result.changed) == (False, True)
    assert (again.receipt.condition, again.receipt.effect) == (
        OperationTerminalCondition.SUCCEEDED,
        OperationEffect.NONE,
    )
    assert (unchanged.enrolled, unchanged.changed) == (False, False)
    # The result carries the real identifier; the command hides it unless identifiers are revealed.
    assert result.profile_id == profile.profile_id
    assert str(profile.profile_id) not in json.dumps(printed.default)
    assert_prints(json_document(result), printed)
    assert_prints(json_document(unchanged), printed_again)
    assert record.profile_id == str(profile.profile_id)
    assert not any(passphrase)
    for private in (PROFILE_INPUT, _WRONG_INPUT):
        assert private.encode("utf-8") not in stored
        assert private not in caplog.text
        assert all(private not in repr(entry.__dict__) for entry in caplog.records)


def _access_context(
    registry: OperationRegistry, profile_id: UUID, frontend: OperationFrontendProjection, action: AccessAction
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=UUID(int=7),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(RECOVERY_REVOKE_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )


def test_every_frontend_gets_the_same_decision_for_the_same_request() -> None:
    definition, registration = recovery_revoke_operation()
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    profile_id = uuid4()
    request = OperationRequest(
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=RecoveryRevokeRequest(profile_id=profile_id),
    )
    command_line = OperationFrontendProjection.CLI

    for action in AccessAction:
        decisions: dict[OperationFrontendProjection, object] = {}
        for frontend in OperationFrontendProjection:
            context = _access_context(registry, profile_id, frontend, action)
            try:
                resolved = resolve_operation_access(registry=registry, request=request, context=context)
            except ProfileAccessRefusedError as refused:
                decisions[frontend] = refused.reason
            else:
                assert resolved.request.frontend is frontend
                decisions[frontend] = (resolved.policy, resolved.request.model_dump(exclude={"frontend"}))
        assert len(decisions) == 3
        assert all(decision == decisions[command_line] for decision in decisions.values())
        assert (decisions[command_line] is AccessDenialCode.OPERATION_DENIED) == (
            action not in SINGLE_RUN_COMMITTING_ACTIONS
        )

    for frontend in OperationFrontendProjection:
        with pytest.raises(ProfileAccessRefusedError) as foreign:
            resolve_operation_access(
                registry=registry,
                request=request,
                context=_access_context(registry, uuid4(), frontend, AccessAction.SUBMIT),
            )
        assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_the_contract_declares_the_one_shot_passphrase_and_no_secret_in_its_schemas() -> None:
    _definition, registration = recovery_revoke_operation()
    contract = registration.contract

    assert contract.ephemeral_secret_required
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == RECOVERY_REVOKE_OPERATION_DEFINITION_ID + ".result"
    assert set(RecoveryRevokeRequest.model_fields) == {"profile_id"}
    assert set(RecoveryRevokeProjection.model_fields) == {"profile_id", "enrolled", "changed"}
