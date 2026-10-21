"""A shared public refusal code is logged with the check that actually refused.

``runtime_peer_untrusted`` answers many distinct checks. The wire keeps the one
public code; the runtime's own log names which check fired, so an operator can
tell a peer that is not the verified desktop holder from any other peer
refusal.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .stored_sign_in_runtime import stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_desktop_frontend_claim_by_a_generic_peer_logs_its_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG), stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        client = FrontendClient(
            runtime.connect(), profile_id=runtime.profile_id, frontend=OperationFrontendProjection.DESKTOP
        )
        with pytest.raises(RefusalError) as refused:
            client.resume_receipt()

    assert refused.value.reason is RefusalCode.PEER_UNTRUSTED
    records = [
        record for record in caplog.records if getattr(record, "failure_boundary", None) == "profile_request_refused"
    ]
    assert [record.__dict__["reason"] for record in records] == ["desktop_holder_descriptor_absent"]
    (record,) = records
    assert record.levelno == logging.WARNING
    assert record.__dict__["error_code"] is not None
    assert str(record.__dict__["error_origin"]).startswith(
        "cadrumo_runtime.host.profile_connection_services:_verify_desktop_holder:"
    )
    assert "desktop_holder_descriptor_absent" not in str(refused.value)
