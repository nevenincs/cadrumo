"""Real-behavior tests for the shared sandbox-notice / JSON-emit funnel.

No mocks: every case writes a real plaintext bucket manifest (mirroring
exactly what ``profile create`` / ``sandbox create`` materialise) under an
isolated storage root and drives the real
:func:`~cadrumo.core.resolve_active_bucket_id` precedence chain through
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
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.json_contract import NoticeSeverity, OutputSchema, register_schema
from ....tests.secure_sql import isolated_profile_storage_root
from .. import emit_operator_json_success, sandbox_banner_line, sandbox_notice_for_active_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MANIFEST_CREATED_AT = datetime(2026, 7, 25, 9, 0, 0, tzinfo=UTC)
_SANDBOX_CODE = "config.profile.sandbox.active_indicator"


@register_schema("operator_output.tests.probe")
class _ProbeResult(OutputSchema):
    """Throwaway registered result schema, local to this test module."""

    label: str


def _write_bucket_manifest(root: Path, *, bucket_id: str, label: str) -> None:
    """Write a real plaintext ``manifest.toml``, exactly as ``profile create`` does."""
    from ....adapters.persistence.storage.bucket import (
        BucketManifest,
        bucket_paths,
        provision_bucket_directory,
        write_manifest,
    )
    from ....adapters.persistence.storage.master_key import KdfParams
    from ....domain.user_profile import UserProfileStatus

    provision_bucket_directory(root, bucket_id)
    write_manifest(
        bucket_paths(root, bucket_id),
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=_MANIFEST_CREATED_AT,
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=UserProfileStatus.ACTIVE,
        ),
    )


def test_sandbox_notice_absent_when_no_active_bucket(tmp_path: Path) -> None:
    """No active-profile pointer/override at all: no notice, no I/O failure."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert sandbox_notice_for_active_bucket() is None


def test_sandbox_notice_absent_for_a_real_non_sandbox_profile(tmp_path: Path) -> None:
    """A real profile bucket (ordinary label) never gets annotated."""
    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _write_bucket_manifest(storage_root, bucket_id=bucket_id, label="operator")
        with override_settings(cadrumo_active_profile=bucket_id):
            assert sandbox_notice_for_active_bucket() is None


def test_sandbox_notice_present_for_an_active_sandbox_bucket(tmp_path: Path) -> None:
    """A sandbox-labelled active bucket surfaces the persistent info notice."""
    bucket_id = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _write_bucket_manifest(storage_root, bucket_id=bucket_id, label="sandbox:bakeoff")
        with override_settings(cadrumo_active_profile=bucket_id):
            notice = sandbox_notice_for_active_bucket()

    assert notice is not None
    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == _SANDBOX_CODE
    assert "sandbox:bakeoff" in notice.message
    assert notice.suggestion == "aeat config profile sandbox discard"


def test_sandbox_banner_line_is_a_tab_delimited_sandbox_prefixed_line(tmp_path: Path) -> None:
    """The text-mode banner shares the exact notice message, tab-prefixed with SANDBOX."""
    bucket_id = "8f2c1a9e-4b3d-4c5e-9f6a-7b8c9d0e1f2a"
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _write_bucket_manifest(storage_root, bucket_id=bucket_id, label="sandbox:banner-probe")
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

    bucket_id = "9a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9"
    caller_notice = Notice(severity=NoticeSeverity.INFO, code="probe.caller_notice", message="caller-supplied")
    result = _ProbeResult(label="probe")

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _write_bucket_manifest(storage_root, bucket_id=bucket_id, label="sandbox:emit-probe")
        with override_settings(cadrumo_active_profile=bucket_id):
            emit_operator_json_success(
                "operator_output.tests.probe",
                result,
                notices=(caller_notice,),
                active_profile="probe",
            )

    document = json.loads(capsys.readouterr().out)
    codes = [notice["code"] for notice in document["notices"]]
    assert codes == [_SANDBOX_CODE, "probe.caller_notice"]
    assert document["result"]["label"] == "probe"


def test_emit_operator_json_success_omits_sandbox_notice_when_not_sandbox(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real (non-sandbox) profile emits only the caller-supplied notices."""
    from ....core.json_contract import Notice

    bucket_id = "1c2d3e4f-5061-7283-94a5-b6c7d8e9f0a1"
    caller_notice = Notice(severity=NoticeSeverity.INFO, code="probe.caller_notice", message="caller-supplied")
    result = _ProbeResult(label="probe")

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _write_bucket_manifest(storage_root, bucket_id=bucket_id, label="operator")
        with override_settings(cadrumo_active_profile=bucket_id):
            emit_operator_json_success(
                "operator_output.tests.probe",
                result,
                notices=(caller_notice,),
                active_profile="probe",
            )

    document = json.loads(capsys.readouterr().out)
    codes = [notice["code"] for notice in document["notices"]]
    assert codes == ["probe.caller_notice"]
