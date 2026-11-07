"""A profile worker that dies while it starts is reported by exit status and frame identifiers, never output text."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.diagnostic_log import DiagnosticFormatter
from cadrumo.core.logging import LOG_FILE_FORMAT
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo.tests.log_records import delivered_records, delivered_text
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from .. import profile_worker
from ..profile_worker import ProfileWorkerProcess, unreturned_profile_worker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
]

_CANARY_TAX_ID = "12345678Z"
_CANARY_VALUE = "exit-reason-canary-secret"
_CANARY_NAME = "Lucía Fernández Ortega"
_MESSAGE_TEXT = "no authority root"


def _import_crashing_worker(tmp_path: Path) -> Path:
    """A worker entry whose first import computes a value that cannot exist yet, as an unconfigured clock did."""
    clock = tmp_path / "authority_clock.py"
    clock.write_text(
        "import sys\n"
        f"raise LookupError('{_MESSAGE_TEXT} for {_CANARY_NAME} {_CANARY_TAX_ID} password={_CANARY_VALUE}')\n",
        encoding="utf-8",
    )
    script = tmp_path / "import_crash_worker.py"
    script.write_text(
        "import importlib.util\n"
        "import sys\n"
        "for index in range(64):\n"
        "    sys.stderr.write(f'early filler line {index} for {sys.argv[0]}\\n')\n"
        f"spec = importlib.util.spec_from_file_location('authority_clock', {str(clock)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n",
        encoding="utf-8",
    )
    return script


def _identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


def test_a_worker_that_dies_at_import_names_its_exit_and_frames_promptly_without_any_output_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    script = _import_crashing_worker(tmp_path)
    root = tmp_path / "storage"
    root.mkdir()
    caplog.set_level(logging.DEBUG, logger=profile_worker.__name__)
    started = time.monotonic()
    with pytest.raises(RefusalError) as refused:
        ProfileWorkerProcess(_identity(), storage_root=root, worker_script=script)
    elapsed = time.monotonic() - started
    candidate = unreturned_profile_worker(refused.value)
    if candidate is not None:
        candidate.settle(deadline=time.monotonic() + HANG_GUARD_SECONDS)

    # The exit wakes the startup wait: no startup deadline is spent waiting for a dead child.
    assert elapsed < HANG_GUARD_SECONDS / 4, elapsed
    assert refused.value.reason is RefusalCode.CONNECTION_CLOSED
    assert refused.value.check == "profile_worker_exited"

    exits = [
        record
        for record in delivered_records(caplog, profile_worker.__name__)
        if record.getMessage() == "profile_worker_exited"
    ]
    assert len(exits) == 1, [record.getMessage() for record in delivered_records(caplog, profile_worker.__name__)]
    exited = exits[0].__dict__
    assert exited["exit_code"] == 1
    assert exited["phase"] == "startup"
    assert exited["worker_error_type"] == "LookupError"
    assert exited["worker_error_origin"] == "authority_clock.py:2:<module>"
    frames = exited["worker_error_frames"]
    assert isinstance(frames, str)
    assert frames.startswith("authority_clock.py:2:<module> <- <frozen importlib._bootstrap")
    assert frames.endswith(" <- import_crash_worker.py:7:<module>")
    assert "stderr_tail" not in exited

    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(exits[0])
    for field in ('"exit_code":1', '"worker_error_type":"LookupError"', '"worker_error_frames":'):
        assert field in rendered, rendered
    for text in (rendered, delivered_text(caplog), str(refused.value), repr(refused.value)):
        for private in (_CANARY_TAX_ID, _CANARY_VALUE, _CANARY_NAME, "Lucía", "Fernández", "Ortega"):
            assert private not in text
        # No line of the output itself leaves the parse: not the message, the filler or a directory.
        for output_text in (_MESSAGE_TEXT, "early filler", "Traceback", str(tmp_path)):
            assert output_text not in text
    assert str(refused.value) == RefusalCode.CONNECTION_CLOSED.value
