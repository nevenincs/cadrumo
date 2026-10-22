"""Expendable peer that opens a verified authorization channel, hands its pipe end to its parent and exits.

The pipe instance outlives the process that was verified on it, which is what
an incarnation recheck must catch.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo_client.contracts.contracts import ServerHello
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.product_version import installed_product_version
from cadrumo_client.transport.windows_channel import WindowsChannel

from ..connection_handshake import accept_connection_handshake
from ..worker_authorization import worker_authorization_namespace
from ..worker_authorization_connections import WorkerAuthorizationConnections
from ..worker_transport import worker_endpoint


class IncarnationSeed(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: ProfileWorkerIdentity
    parent_pid: int
    role: Literal["worker", "runtime"]


def _mark(root: Path, name: str, text: str) -> None:
    pending = root / f"{name}.pending"
    pending.write_text(text, encoding="ascii")
    pending.replace(root / name)


def _hand_to_parent(root: Path, channel: WindowsChannel, parent_pid: int) -> object:
    """Duplicate this end of the pipe into the parent, so the pipe stays open after this process ends.

    The returned duplicate names a handle of the parent; the caller keeps it, unclosed, until it exits.
    """
    import win32api
    import win32con

    parent = win32api.OpenProcess(win32con.PROCESS_DUP_HANDLE, False, parent_pid)
    # The raw pipe end is what is handed over.
    handle = channel._handle
    assert handle is not None
    duplicate = win32api.DuplicateHandle(
        win32api.GetCurrentProcess(), int(handle), parent, 0, False, win32con.DUPLICATE_SAME_ACCESS
    )
    _mark(root, "handle", str(int(duplicate)))
    return duplicate


def main(root: Path, seed: IncarnationSeed) -> None:
    _mark(root, "peer.pid", str(os.getpid()))
    while not (root / "listening").exists():
        time.sleep(0.01)
    if seed.role == "worker":
        # A verified worker connection, exactly as the pool opens it.
        connections = WorkerAuthorizationConnections(identity=seed.identity, root=root, parent_pid=seed.parent_pid)
        channel = connections.checkout(time.monotonic() + 10)
    else:
        # A runtime's end of one verified connection, accepted and answered like the real server's.
        endpoint = worker_endpoint(
            storage_root=root, worker_namespace=worker_authorization_namespace(seed.identity.worker_id)
        )
        endpoint.listen()
        _mark(root, "serving", "1")
        channel = endpoint.accept(timeout=30)
        accept_connection_handshake(
            channel,
            identity=ServerHello(
                product_version=installed_product_version(),
                storage_identity=endpoint.storage_identity,
                boot_id=seed.identity.runtime_boot_id,
            ),
            deadline=time.monotonic() + 10,
        )
        endpoint.close()
    assert isinstance(channel, WindowsChannel)
    handed = _hand_to_parent(root, channel, seed.parent_pid)
    # Exit without finalizers: the duplicate must never be closed as if it were this process's handle.
    os._exit(0 if handed is not None else 1)


if __name__ == "__main__":
    fixture_root = Path(sys.argv[1])
    main(fixture_root, IncarnationSeed.model_validate_json((fixture_root / "seed.json").read_bytes()))
