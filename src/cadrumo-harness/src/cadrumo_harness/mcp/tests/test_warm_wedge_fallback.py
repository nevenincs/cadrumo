"""Warm-transport wedge detection degrades to the subprocess, then recovers.

The warm in-process transport serialises on a single stdout-capture lock (the CLI
writes to the process-global ``sys.stdout``). A verb that hung while holding that
capture would wedge the WHOLE warm transport - a worse blast radius than the
per-call subprocess model the warm transport exists to eliminate. So a warm-eligible
call fails fast: if a prior worker has held the capture past the wedge threshold
the transport is declared wedged and the call degrades to the proven supervised
subprocess transport, carrying a warning Notice that names the wedge; when the
wedged worker finally completes and releases the capture, warm serving resumes.

This test drives the REAL wedge detector (:func:`warm_capture_holder_age` and the
wedge/degrade branch of ``_run_tool``) against the REAL capture lock and the REAL
shared holder state. A real thread reproduces a wedged worker by acquiring the
production capture lock and recording the holder timestamp exactly as
``run_cli_in_process`` does, then holding it until the test releases it. The
degraded call runs a REAL ``aeat`` subprocess and the recovered call a REAL warm
in-process dispatch - no stubbed detector, no faked transport.
"""

from __future__ import annotations

import threading
import time

import pytest

from .. import _inprocess
from .._inprocess import warm_capture_holder_age
from .._settings import override_mcp_settings
from .._tools import McpToolDescriptor, build_tool_descriptors
from .._transport import McpTransport, _attested_cli_executable, _run_tool

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WARM_DEGRADED_NOTICE = "mcp.serving.warm_transport_degraded"


def _descriptor(command_key: str) -> McpToolDescriptor:
    return next(candidate for candidate in build_tool_descriptors() if candidate.command_key == command_key)


def _notice_codes(envelope: dict[str, object]) -> list[str]:
    notices = envelope.get("notices")
    if not isinstance(notices, list):
        return []
    return [str(notice.get("code")) for notice in notices if isinstance(notice, dict)]


def test_wedged_warm_transport_degrades_to_subprocess_then_recovers() -> None:
    descriptor = _descriptor("registry.inspect")
    holding = threading.Event()
    release = threading.Event()

    def _wedged_worker() -> None:
        # Reproduce a warm worker that acquired the capture and overran its ceiling:
        # hold the REAL capture lock and set the REAL holder timestamp exactly as
        # run_cli_in_process does, then keep it held (the wedge) until released.
        _inprocess._CAPTURE_LOCK.acquire()
        with _inprocess._STATE_LOCK:
            _inprocess._HOLDER_SINCE = time.monotonic()
        holding.set()
        try:
            release.wait(timeout=30.0)
        finally:
            with _inprocess._STATE_LOCK:
                _inprocess._HOLDER_SINCE = None
            _inprocess._CAPTURE_LOCK.release()

    worker = threading.Thread(target=_wedged_worker, name="test-wedged-holder", daemon=True)
    worker.start()
    try:
        assert holding.wait(timeout=5.0)
        # A tiny wedge threshold makes the held capture read as wedged at once.
        with override_mcp_settings(
            cadrumo_mcp_wedge_threshold_seconds=0.01,
            cadrumo_mcp_warm_capture_wait_seconds=0.05,
        ):
            time.sleep(0.05)
            assert (warm_capture_holder_age() or 0.0) >= 0.01
            degraded = _run_tool(descriptor, {})
        # A concurrent call degraded to the proven subprocess transport, and the
        # degradation is visible: a warning Notice names the wedge and the outcome
        # records the fallback transport while the executable stays the attested
        # environment CLI (the installed-cohort identity, on every transport).
        assert degraded.transport is McpTransport.SUBPROCESS_FALLBACK
        assert degraded.executable == _attested_cli_executable()
        assert degraded.envelope["status"] == "warning"
        assert _WARM_DEGRADED_NOTICE in _notice_codes(degraded.envelope)
    finally:
        release.set()
        worker.join(timeout=10.0)

    # Completion cleared the wedge: the capture is free and warm serving resumes.
    assert warm_capture_holder_age() is None
    recovered = _run_tool(descriptor, {})
    assert recovered.transport is McpTransport.INPROCESS
    assert recovered.executable == _attested_cli_executable()
    assert _WARM_DEGRADED_NOTICE not in _notice_codes(recovered.envelope)


def test_warm_capture_holder_age_is_none_when_the_capture_is_free() -> None:
    assert warm_capture_holder_age() is None
