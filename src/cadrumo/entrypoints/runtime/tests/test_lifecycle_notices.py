"""Upgrade notices are coalesced and written before a bounded idle stop."""

import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Literal, cast
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from cadrumo.adapters.local_runtime.runtime_frame_io import decode_document, document_frame
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeExitReason,
    RuntimePeer,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.login import RuntimeLoginEvidence
from cadrumo.application.runtime.session_events import RuntimeLifecycleNotice
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.session_events import RuntimeSessionEvents
from cadrumo.entrypoints.runtime.shutdown import RuntimeStop

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context(*, capable: bool = True) -> RuntimeConnectionContext:
    return RuntimeConnectionContext(uuid4(), uuid4(), RuntimePeer(os_owner_id="fixture", process_id=1), capable)


def test_legacy_hello_omits_capability_and_legacy_connection_gets_no_notice() -> None:
    hello = RuntimeClientHello(product_version="1.0.0", storage_identity="a" * 64)
    assert b"lifecycle_notices" not in document_frame(hello)
    events = RuntimeSessionEvents()
    legacy = _context(capable=False)
    events.connect(legacy)
    assert events.upgrade_pending(legacy) is None
    assert events.take(legacy) == ()


class LegacyHello(BaseModel):
    """Frozen pre-notice protocol-3 schema, exposing the one-way compatibility limit."""

    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["client_hello"]
    protocol_version: Literal[3]
    product_version: str
    storage_identity: str
    authority_generation: str | None


def test_opt_in_refuses_on_prior_strict_server_without_silent_downgrade() -> None:
    legacy = RuntimeClientHello(product_version="1.0.0", storage_identity="a" * 64)
    assert decode_document(document_frame(legacy)[5:], LegacyHello).protocol_version == 3
    opted_in = legacy.model_copy(update={"lifecycle_notices": "v1"})
    with pytest.raises(RuntimeRefusalError):
        decode_document(document_frame(opted_in)[5:], LegacyHello)
    assert RuntimeClientHello.model_validate_json(document_frame(legacy)[5:]).lifecycle_notices is None


def test_only_exact_successful_write_acknowledges_notice_and_retries_coalesce() -> None:
    events = RuntimeSessionEvents()
    context = _context()
    events.connect(context)
    flushed = events.upgrade_pending(context)
    assert flushed is not None and not flushed.is_set()
    assert events.upgrade_pending(context) is flushed
    (notice,) = events.take(context)
    assert isinstance(notice, RuntimeLifecycleNotice)
    assert not flushed.is_set()  # Taking/queueing is not delivery.
    events.flushed(_context(), notice)
    assert not flushed.is_set()
    events.flushed(context, notice)
    assert flushed.is_set()
    assert events.upgrade_pending(context) is flushed
    assert events.take(context) == ()


@pytest.mark.parametrize(
    "frontend,unlocked",
    [
        (OperationFrontendProjection.TUI, True),
        (OperationFrontendProjection.CLI, True),
        (OperationFrontendProjection.MCP, True),
        (OperationFrontendProjection.TUI, False),
    ],
)
def test_idle_stop_waits_only_for_attended_opted_in_connections(
    tmp_path: Path, frontend: OperationFrontendProjection, unlocked: bool
) -> None:
    stop = RuntimeStop()
    context = _context(capable=frontend is not OperationFrontendProjection.MCP)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="a" * 64, runtime_boot_id=context.runtime_boot_id, stop=stop
    )
    login = cast(
        RuntimeLoginEvidence,
        SimpleNamespace(
            observe=lambda **_: SimpleNamespace(active=True, unlocked=unlocked, os_owner_id=context.peer.os_owner_id)
        ),
    )
    profiles._capture = lambda _: login
    profiles.connect_events(context, cast(RuntimeByteChannel, SimpleNamespace(peer=context.peer)))
    assert not profiles._connections  # No profile login or session is required for presentation.
    attended = frontend is not OperationFrontendProjection.MCP and unlocked
    began = time.monotonic()
    assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.02) is (not attended)
    assert time.monotonic() - began < 0.5
    if attended:
        assert not stop.is_set()
        assert profiles._admitting()
        (notice,) = profiles.take_events(context)
        profiles.event_flushed(context, notice)
        assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.2)
        assert stop.is_set()
    else:
        assert profiles.take_events(context) == ()


def test_slow_native_observation_is_bounded_retained_and_cannot_publish_late(tmp_path: Path) -> None:
    stop = RuntimeStop()
    context = _context()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="a" * 64, runtime_boot_id=context.runtime_boot_id, stop=stop
    )
    entered, release = Event(), Event()
    calls: list[int] = []
    blocking = False

    def observe(**_: object) -> SimpleNamespace:
        if blocking:
            calls.append(1)
            entered.set()
            assert release.wait(2)
        return SimpleNamespace(active=True, unlocked=True, os_owner_id=context.peer.os_owner_id)

    profiles._capture = lambda _: cast(RuntimeLoginEvidence, SimpleNamespace(observe=observe))
    profiles.connect_events(context, cast(RuntimeByteChannel, SimpleNamespace(peer=context.peer)))
    blocking = True
    try:
        began = time.monotonic()
        assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.01)
        assert time.monotonic() - began < 0.15
        assert entered.wait(0.2)
        retained = profiles._notice_observation
        assert retained is not None and not retained.done()
        # Retry storms cannot accumulate OS queries or reuse a timed-out task.
        for _ in range(20):
            assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.01)
            assert profiles._notice_observation is retained
        assert len(calls) == 1
        assert not stop.is_set() and profiles._admitting()
        assert profiles.take_events(context) == ()
    finally:
        release.set()
    assert retained.result(timeout=1) is None
    assert profiles.take_events(context) == () and not stop.is_set()
    # A later attempt requires a fresh native observation and a real frame flush.
    assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.02)
    assert len(calls) == 2
    (notice,) = profiles.take_events(context)
    profiles.event_flushed(context, notice)
    assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.2)
    assert len(calls) == 3 and stop.is_set()
