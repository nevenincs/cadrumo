"""Finite installed MainPID for native managed-runtime stop acceptance."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path
from threading import Event
from uuid import uuid4

# The test's exact owner-controlled launcher names this checked-out source file
# and an ext4 virtualenv explicitly. No inherited PYTHONPATH or login shell is
# trusted by the installed process.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from cadrumo.adapters.local_runtime.linux_managed_stop import LinuxManagedRuntimeStop
from cadrumo.adapters.local_runtime.posix import PosixRuntimeEndpoint, posix_storage_identity
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLoginContext,
)

_VERSION = "synthetic-cohort"


class _OwnerObservation:
    login_id = "synthetic-managed-runtime-owner"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=str(os.getuid()),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _binding(root: Path) -> RuntimeServiceBinding:
    return RuntimeServiceBinding(
        executable=str(root / "synthetic-runtime"),
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version=_VERSION,
    )


def _foreign_stop(root: Path) -> int:
    """Probe the callback from a process that is not systemd's MainPID."""
    try:
        LinuxManagedRuntimeStop(_binding(root))()
    except RuntimeRefusalError as error:
        return 0 if error.reason is RuntimeRefusalCode.PEER_UNTRUSTED else 2
    return 3


def _service(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--storage-root", required=True)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--managed-session", action="store_true")
    options = parser.parse_args(arguments)
    root = Path(options.storage_root)
    binding = _binding(root)
    if (
        root.resolve(strict=True) != (root / "synthetic-runtime").resolve(strict=True).parent
        or options.storage_identity != binding.storage_identity
        or options.expected_version != binding.product_version
        or not options.managed_session
    ):
        return 2

    stop = Event()

    def terminate(_number: int, _frame: object) -> None:
        (root / "term").write_text(str(os.getpid()), encoding="ascii")
        stop.set()

    def lifetime_expired(_number: int, _frame: object) -> None:
        # Successful finite exit prevents Restart=on-failure from reviving an
        # orphaned fixture if the requesting test process disappears.
        os._exit(0)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGALRM, lifetime_expired)
    signal.alarm(45)
    endpoint = PosixRuntimeEndpoint(storage_root=root)
    server = RuntimeTransportServer(
        endpoint,
        product_version=_VERSION,
        stop=stop,
        boot_id=uuid4(),
        capture_owner_login=lambda _channel: _OwnerObservation(),
        prepare_owner_stop=LinuxManagedRuntimeStop(binding),
    )
    count_path = root / "boot-count"
    count = int(count_path.read_text(encoding="ascii")) + 1 if count_path.exists() else 1
    count_path.write_text(str(count), encoding="ascii")
    (root / "boot").write_text(str(os.getpid()), encoding="ascii")
    try:
        server.serve()
        (root / "settled").write_text("yes", encoding="ascii")
        return 0
    finally:
        endpoint.close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "foreign-stop":
        raise SystemExit(_foreign_stop(Path(sys.argv[2])))
    raise SystemExit(_service(sys.argv[1:]))
