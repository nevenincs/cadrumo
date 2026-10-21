"""An expired attended service lease must not retire its human parent."""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest

from ...application import session_authority_admission
from .test_service_records import RECORD_CAPABILITY, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_service_lease_renews_after_expiry_without_losing_human_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        # Shorten only this fixture's child lease, after cold human admission.
        monkeypatch.setattr(session_authority_admission, "ACCESS_LEASE_MAXIMUM", timedelta(seconds=4))
        service = runtime.connect_service()
        runtime.admit(service)
        original = service.claim()
        assert original is not None
        record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
        assert record.state == "absent" and not material
        # Let both the worker's idle expiry and the runtime's lease sweep run
        # without service polling keeping the control pipe active.
        time.sleep(4.5)
        deadline = time.monotonic() + 8
        renewed = original
        while renewed.session_id == original.session_id and time.monotonic() < deadline:
            time.sleep(0.1)
            claimed = service.claim()
            assert claimed is not None, "expiry lost the live person's service approval"
            renewed = claimed
        assert renewed.session_id != original.session_id
        assert renewed.parent_session_id == runtime.person_session_id
        assert renewed.lease_id == original.lease_id
        record, material = service.record_read(RECORD_CAPABILITY, "synthetic-expiry")
        assert record.state == "absent" and not material
