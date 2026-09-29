"""On-demand control of exact existing user-systemd provisioning, without lingering."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
    RuntimeServiceBinding,
)
from .manager_commands import NativeManagerCommand, run_manager_command
from .posix import posix_owner_uid, posix_storage_identity
from .service_definitions import linux_user_service, runtime_service_name

_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "FragmentPath",
    "DropInPaths",
    "UnitFileState",
    "NeedDaemonReload",
)


def _fragment_flags() -> int:
    if sys.platform == "linux":
        return os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _properties(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in _PROPERTIES or key in values:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        values[key] = value
    if set(values) != set(_PROPERTIES):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return values


def _exact_fragment(path: str, expected: str) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    descriptor: int | None = None
    try:
        target = Path(path)
        if not target.is_absolute():
            return False
        for parent in target.parents:
            metadata = parent.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid not in (0, posix_owner_uid()):
                return False
            if metadata.st_mode & 0o022 and not metadata.st_mode & stat.S_ISVTX:
                return False
        descriptor = os.open(target, _fragment_flags())
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid not in (0, posix_owner_uid())
            or metadata.st_mode & 0o022
            or metadata.st_size > 64 * 1024
        ):
            return False
        return os.read(descriptor, 64 * 1024 + 1) == expected.encode("utf-8")
    except OSError:
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


class LinuxUserManager:
    """Control only a verified current unit; manager existence grants no access."""

    _definition: str
    _name: str

    def __init__(self, binding: RuntimeServiceBinding) -> None:
        """Bind the native UID and physical root before consulting user systemd."""
        if not sys.platform.startswith("linux"):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if binding.os_owner_id != str(posix_owner_uid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if binding.storage_identity != posix_storage_identity(Path(binding.storage_root)):
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        self._definition = linux_user_service(binding)
        self._name = runtime_service_name(binding) + ".service"

    async def inspect(self) -> RuntimeManagerInspection:
        """Refuse modified fragments, drop-ins, stale manager loads and unknown states."""
        try:
            response = await run_manager_command(
                NativeManagerCommand.SYSTEMCTL,
                (
                    "--user",
                    "--no-pager",
                    "--no-ask-password",
                    "show",
                    self._name,
                    "--property=" + ",".join(_PROPERTIES),
                ),
            )
            if response.returncode != 0 and not response.output:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            values = _properties(response.output)
            if response.returncode != 0 and values["LoadState"] != "not-found":
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            provisioned = values["LoadState"] == "loaded"
            matches = (
                provisioned
                and not values["DropInPaths"]
                and values["NeedDaemonReload"] == "no"
                and values["UnitFileState"] in {"enabled", "disabled"}
                and _exact_fragment(values["FragmentPath"], self._definition)
            )
            return RuntimeManagerInspection(
                kind=RuntimeManagerKind.LINUX_USER_SERVICE,
                available=True,
                provisioned=provisioned,
                binding_matches=matches,
                login_autostart=values["UnitFileState"] == "enabled",
                process_state={
                    "active": RuntimeManagerProcessState.RUNNING,
                    "activating": RuntimeManagerProcessState.STARTING,
                    "inactive": RuntimeManagerProcessState.STOPPED,
                    "failed": RuntimeManagerProcessState.STOPPED,
                }.get(values["ActiveState"], RuntimeManagerProcessState.UNKNOWN),
            )
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.UNAVAILABLE:
                raise
            return RuntimeManagerInspection(
                kind=RuntimeManagerKind.LINUX_USER_SERVICE,
                available=False,
                provisioned=False,
                binding_matches=False,
                login_autostart=False,
                process_state=RuntimeManagerProcessState.UNKNOWN,
            )

    async def _control(self, verb: str) -> None:
        current = await self.inspect()
        if not current.available or not current.provisioned:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if not current.binding_matches:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        response = await run_manager_command(
            NativeManagerCommand.SYSTEMCTL,
            ("--user", "--no-pager", "--no-ask-password", "--no-block", verb, self._name),
        )
        if response.returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    async def start(self) -> None:
        """Queue start without enabling the unit, changing login state or lingering."""
        await self._control("start")

    async def stop(self) -> None:
        """Queue stop to signal main-process drain and suppress automatic restart.

        The exact unit's mixed kill policy leaves descendants available for the
        bounded application drain. Successful queuing is not settlement.
        """
        await self._control("stop")
