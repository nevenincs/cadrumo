"""Real-behavior tests for the shared sandbox-notice / JSON-emit funnel.

No mocks: every case creates a real committed custody capsule under an
isolated storage root and drives the real
:func:`~cadrumo.core.bucket_pointer.resolve_active_bucket_id` precedence chain through
:func:`~cadrumo.core.config.override_settings`.

These tests pin two structural guarantees: the sandbox-active indicator is
present in BOTH JSON and text-mode output whenever the active bucket is a
sandbox, and :func:`emit_operator_json_success` — not
``core.json_contract.emit_json_success`` directly — is what every
operator-facing command surface (the CLI transport and the setup wizard
alike) must call to get it.
"""

from __future__ import annotations

import json
from base64 import b64encode
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....core.config import override_settings
from ....core.json_contract import NoticeSeverity, OutputSchemaError
from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ....tests.profile_capsule import mint_test_profile_recovery_envelope
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile.lifecycle import ProfileCapsuleLifecycle
from ...user_profile.capsule_record import ProfileRecordSession
from ...wizard import ConfigProfileCreateResult, ProfileWizardStatus
from .. import emit_operator_json_success, sandbox_banner_line, sandbox_notice_for_active_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SANDBOX_CODE = "config.profile.sandbox.active_indicator"
_DEK = bytes(range(32))


def _create_committed_profile(root: Path, *, bucket_id: str, label: str) -> None:
    """Create and select the real committed capsule that owns the label projection."""
    profile_id = UUID(bucket_id)
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=b64encode(b"e" * 16).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_DEK)
    lifecycle = ProfileCapsuleLifecycle(root=root)
    try:
        lifecycle.create(
            label=label,
            profile_id=profile_id,
            password_envelope=envelope,
            sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
            data_files={},
            recovery_envelope=mint_test_profile_recovery_envelope(profile_id, dek=_DEK, dek_epoch=envelope.dek_epoch),
            initial_record=UserProfileRecord(
                profile_id=bucket_id,
                setup_state=ProfileSetupState.INCOMPLETE,
            ),
            record_session=session,
        )
        lifecycle.select(label)
    finally:
        session.close()


def test_sandbox_notice_absent_when_no_active_bucket(tmp_path: Path) -> None:
    """No active-profile pointer/override at all: no notice, no I/O failure."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert sandbox_notice_for_active_bucket() is None


def test_sandbox_notice_absent_for_a_real_non_sandbox_profile(tmp_path: Path) -> None:
    """A real profile bucket (ordinary label) never gets annotated."""
    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_committed_profile(storage_root, bucket_id=bucket_id, label="operator")
        with override_settings(cadrumo_active_profile=bucket_id):
            assert sandbox_notice_for_active_bucket() is None


def test_sandbox_notice_present_for_an_active_sandbox_bucket(tmp_path: Path) -> None:
    """A sandbox-labelled active bucket surfaces the persistent info notice."""
    bucket_id = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_committed_profile(storage_root, bucket_id=bucket_id, label="sandbox:bakeoff")
        with override_settings(cadrumo_active_profile=bucket_id):
            notice = sandbox_notice_for_active_bucket()

    assert notice is not None
    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == _SANDBOX_CODE
    assert "sandbox:bakeoff" in notice.message
    assert notice.action is None


def test_sandbox_banner_line_is_a_tab_delimited_sandbox_prefixed_line(tmp_path: Path) -> None:
    """The text-mode banner shares the exact notice message, tab-prefixed with SANDBOX."""
    bucket_id = "8f2c1a9e-4b3d-4c5e-9f6a-7b8c9d0e1f2a"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_committed_profile(storage_root, bucket_id=bucket_id, label="sandbox:banner-probe")
        with override_settings(cadrumo_active_profile=bucket_id):
            notice = sandbox_notice_for_active_bucket()

    assert notice is not None
    line = sandbox_banner_line(notice)
    assert line == f"SANDBOX\t{notice.message}"
    assert line.startswith("SANDBOX\t")


def test_emit_operator_json_success_prepends_sandbox_notice_when_active(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The funnel injects the sandbox notice ahead of caller-supplied notices.

    This is the structural guarantee the widened
    ``test_no_bare_emit_json_success_call`` gate protects: any command
    surface that routes through this function — rather than calling
    ``core.json_contract.emit_json_success`` directly — gets the sandbox
    indicator for free, without having to ask for it.
    """
    from ....core.json_contract import Notice

    bucket_id = "9a1b2c3d-4e5f-4071-8293-a4b5c6d7e8f9"
    caller_notice = Notice(severity=NoticeSeverity.INFO, code="probe.caller_notice", message="caller-supplied")
    result = ConfigProfileCreateResult(profile_name="probe", status=ProfileWizardStatus.CREATED, active_profile="probe")

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_committed_profile(storage_root, bucket_id=bucket_id, label="sandbox:emit-probe")
        with override_settings(cadrumo_active_profile=bucket_id):
            emit_operator_json_success(
                "config.profile.create",
                result,
                notices=(caller_notice,),
                active_profile="probe",
            )

    document = json.loads(capsys.readouterr().out)
    codes = [notice["code"] for notice in document["notices"]]
    assert codes == [_SANDBOX_CODE, "probe.caller_notice"]
    assert document["result"]["profile_name"] == "probe"


def test_emit_operator_json_success_omits_sandbox_notice_when_not_sandbox(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real (non-sandbox) profile emits only the caller-supplied notices."""
    from ....core.json_contract import Notice

    bucket_id = "1c2d3e4f-5061-4283-94a5-b6c7d8e9f0a1"
    caller_notice = Notice(severity=NoticeSeverity.INFO, code="probe.caller_notice", message="caller-supplied")
    result = ConfigProfileCreateResult(profile_name="probe", status=ProfileWizardStatus.CREATED, active_profile="probe")

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_committed_profile(storage_root, bucket_id=bucket_id, label="operator")
        with override_settings(cadrumo_active_profile=bucket_id):
            emit_operator_json_success(
                "config.profile.create",
                result,
                notices=(caller_notice,),
                active_profile="probe",
            )

    document = json.loads(capsys.readouterr().out)
    codes = [notice["code"] for notice in document["notices"]]
    assert codes == ["probe.caller_notice"]


def test_emit_operator_json_success_refuses_an_unregistered_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The operator funnel cannot wrap an arbitrary result under a command key."""
    result = ConfigProfileCreateResult(profile_name="probe", status=ProfileWizardStatus.CREATED, active_profile="probe")

    with pytest.raises(OutputSchemaError, match="has no registered output schema"):
        emit_operator_json_success("operator_output.tests.probe", result)

    assert capsys.readouterr().out == ""


def test_emit_operator_json_success_refuses_a_result_outside_the_registered_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A registered command cannot use the envelope to bypass strict result fields."""
    with pytest.raises(OutputSchemaError, match="does not conform to the registered schema"):
        emit_operator_json_success(
            "config.profile.create",
            {"profile_name": "probe", "status": 1, "active_profile": "probe"},
        )

    assert capsys.readouterr().out == ""
