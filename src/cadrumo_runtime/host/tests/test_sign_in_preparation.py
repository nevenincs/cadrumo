"""A watched, signed-out profile's worker starts before its sign-in, once.

The desktop watches the selected profile's sign-in from the moment its window
opens, long before the person types a password. The runtime uses that watch to
start the profile's worker, so the sign-in meets a worker that has already
imported and connected. The worker holds no key or lease until a sign-in
installs one; preparing twice must not start two, and a preparation that fails
leaves the next watch, or the sign-in itself, to try again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import Peer
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@dataclass
class _Owner:
    fail: bool = False
    prepared: list[UUID] = field(default_factory=list)
    done: Event = field(default_factory=Event)
    profile_id: UUID = field(default_factory=uuid4)

    def prepare(self) -> None:
        self.prepared.append(self.profile_id)
        self.done.set()
        if self.fail:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)


def _service(tmp_path: Path, owner: _Owner, monkeypatch: pytest.MonkeyPatch) -> RuntimeProfileConnections:
    service = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=Event(),
        secret_store=MemoryNativePort,
        os_owner_id="synthetic-owner",
    )
    monkeypatch.setattr(service, "_host", lambda profile_id, context: SimpleNamespace(owner=owner))
    return service


def _context() -> ConnectionContext:
    return ConnectionContext(
        connection_id=uuid4(), runtime_boot_id=uuid4(), peer=Peer(os_owner_id="synthetic-owner", process_id=1)
    )


def _settle(owner: _Owner) -> None:
    assert owner.done.wait(10), "the preparation never ran"
    owner.done.clear()


def test_a_watched_profile_is_prepared_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner()
    service = _service(tmp_path, owner, monkeypatch)
    service.prepare_for_sign_in(owner.profile_id, _context())
    _settle(owner)
    service.prepare_for_sign_in(owner.profile_id, _context())
    assert not owner.done.wait(0.2)
    assert owner.prepared == [owner.profile_id]


def test_a_failed_preparation_is_tried_again_by_the_next_watch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner(fail=True)
    service = _service(tmp_path, owner, monkeypatch)
    service.prepare_for_sign_in(owner.profile_id, _context())
    _settle(owner)
    owner.fail = False
    for _ in range(100):
        service.prepare_for_sign_in(owner.profile_id, _context())
        if owner.done.wait(0.05):
            break
    assert owner.prepared == [owner.profile_id, owner.profile_id]


def test_a_draining_runtime_prepares_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner()
    service = _service(tmp_path, owner, monkeypatch)
    service.stop.set()
    service.prepare_for_sign_in(owner.profile_id, _context())
    assert not owner.done.wait(0.2)
    assert owner.prepared == []
