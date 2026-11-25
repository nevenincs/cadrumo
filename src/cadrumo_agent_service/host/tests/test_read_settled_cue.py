"""A catalog read the desktop was told is busy cues the desktop once when it settles.

The service, its administration and its bounded catalog read run for real; only
the declared catalog, which the read serves while no agent is ready, is held
until the test releases it, and the bound is narrowed so the first request is
told busy at once. The cue is the ``read_settled`` event line the desktop
republishes the agent's status on.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as administration_module
from ...adapters.provider_catalog_metadata import declared_catalog_envelope
from ...providers.domain.record import LocalEngine
from ...service import AgentService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DECLARED = declared_catalog_envelope({"providers": []})
_BUSY = {"kind": "refused", "code": "busy"}
_SETTLE_SECONDS = 10.0


class _Declared:
    """The declared catalog, served once the test releases it."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def __call__(self) -> dict[str, Any]:
        assert self.release.wait(_SETTLE_SECONDS)
        return _DECLARED


@pytest.fixture
def declared(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Declared]:
    held = _Declared()
    monkeypatch.setattr(administration_module, "declared_provider_catalog_response", held)
    monkeypatch.setattr(administration_module, "ADMIN_READ_SECONDS", 0.05)
    yield held
    held.release.set()


def _service(tmp_path: Path, events: list[dict[str, Any]]) -> AgentService:
    client = SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
    return AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=events.append,
    )


def _catalog_work_ended() -> None:
    """Wait until the catalog read's work thread, its cue included, has ended."""
    for thread in threading.enumerate():
        if thread.name == "agent-service-catalog":
            thread.join(_SETTLE_SECONDS)
            assert not thread.is_alive()


def test_a_busy_catalog_read_publishes_one_cue_when_it_settles(tmp_path: Path, declared: _Declared) -> None:
    events: list[dict[str, Any]] = []
    service = _service(tmp_path, events)
    try:
        assert service.admin("catalog") == _BUSY
        assert service.admin("catalog") == _BUSY
        assert events == []
        declared.release.set()
        _catalog_work_ended()
        assert events == [{"event": "read_settled"}]
        # The read the cue sends the desktop back for is served and cues nothing more.
        assert service.admin("catalog") != _BUSY
        assert events == [{"event": "read_settled"}]
    finally:
        service.close()


def test_a_catalog_read_answered_within_its_bound_publishes_no_cue(
    tmp_path: Path, declared: _Declared, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[dict[str, Any]] = []
    service = _service(tmp_path, events)
    declared.release.set()
    monkeypatch.setattr(administration_module, "ADMIN_READ_SECONDS", _SETTLE_SECONDS)
    try:
        assert service.admin("catalog") != _BUSY
        _catalog_work_ended()
        assert events == []
    finally:
        service.close()
