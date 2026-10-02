"""Explicit per-user systemd provisioning and control, without lingering."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
    RuntimeServiceBinding,
)
from ...core.async_cleanup import await_cancellation_complete
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


def _refuse_configuration() -> RuntimeRefusalError:
    return RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)


def _native_home() -> Path:
    if sys.platform != "linux":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pwd

    home = Path(pwd.getpwuid(posix_owner_uid()).pw_dir)
    if not home.is_absolute() or ".." in home.parts:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return home


@contextmanager
def _configuration_directory(*, create: bool) -> Generator[tuple[int, Path]]:
    home = _native_home()
    uid = posix_owner_uid()
    target = home / ".config" / "systemd" / "user"
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for index, part in enumerate(target.parts[1:], start=1):
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
            except FileNotFoundError:
                if not create or index < len(home.parts):
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
            observed = os.fstat(child)
            allowed_sticky_parent = (
                index < len(home.parts) - 1 and observed.st_uid == 0 and observed.st_mode & stat.S_ISVTX
            )
            if (
                observed.st_uid not in (0, uid)
                or (observed.st_mode & 0o022 and not allowed_sticky_parent)
                or (index >= len(home.parts) - 1 and observed.st_uid != uid)
                or (index == len(target.parts) - 1 and stat.S_IMODE(observed.st_mode) != 0o700)
            ):
                os.close(child)
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            os.close(descriptor)
            descriptor = child
        yield descriptor, target
    finally:
        os.close(descriptor)


def _file_identity(observed: os.stat_result) -> tuple[int, ...]:
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_uid,
        observed.st_gid,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _read_configuration(directory: int, name: str) -> bytes | None:
    try:
        descriptor = os.open(name, _fragment_flags(), dir_fd=directory)
    except FileNotFoundError:
        return None
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != posix_owner_uid()
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_nlink != 1
            or observed.st_size > 64 * 1024
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        with os.fdopen(os.dup(descriptor), "rb") as source:
            payload = source.read(64 * 1024 + 1)
        if len(payload) > 64 * 1024 or _file_identity(os.fstat(descriptor)) != _file_identity(observed):
            raise _refuse_configuration()
        return payload
    finally:
        os.close(descriptor)


def _configuration_layout(directory: int, target: Path, name: str) -> None:
    # Refuse even empty matching drop-in directories, including dash-prefix
    # and service-type directories, rather than merging unreviewed settings.
    for entry in _drop_in_names(name):
        try:
            os.stat(entry, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise _refuse_configuration()
    try:
        wants = os.open(
            "default.target.wants", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory
        )
    except FileNotFoundError:
        return
    try:
        observed = os.fstat(wants)
        if observed.st_uid != posix_owner_uid() or observed.st_mode & 0o022:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        try:
            link = os.stat(name, dir_fd=wants, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (
            not stat.S_ISLNK(link.st_mode)
            or link.st_uid != posix_owner_uid()
            or os.readlink(name, dir_fd=wants) not in ("../" + name, str(target / name))
        ):
            raise _refuse_configuration()
    finally:
        os.close(wants)


def _drop_in_names(name: str) -> tuple[str, ...]:
    prefixes = name.removesuffix(".service").split("-")
    return (
        name + ".d",
        "service.d",
        *("-".join(prefixes[:index]) + "-.service.d" for index in range(1, len(prefixes))),
    )


def _manager_unit_paths(output: str, target: Path) -> tuple[Path, ...]:
    # systemctl shell-quotes string-array elements. Only its unquoted path
    # subset is supported here; refuse additional quoting rather than guess.
    prefix, separator, value = output.removesuffix("\n").partition("=")
    raw = value.split(" ")
    if prefix != "UnitPath" or separator != "=" or not 0 < len(raw) <= 64:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    paths: list[Path] = []
    for text in raw:
        path = Path(text)
        if (
            not text
            or len(text) > 4096
            or any(character.isspace() or ord(character) < 32 or character in "\\\"'" for character in text)
            or path.anchor != "/"
            or ".." in path.parts
            or str(path) != text
            or path in paths
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        paths.append(path)
    if target not in paths:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return tuple(paths)


@contextmanager
def _lookup_directory(path: Path) -> Generator[int]:
    if sys.platform != "linux":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
            observed = os.fstat(child)
            if observed.st_uid not in (0, posix_owner_uid()) or (
                observed.st_mode & 0o022 and not (observed.st_uid == 0 and observed.st_mode & stat.S_ISVTX)
            ):
                os.close(child)
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _require_lookup_policy(paths: tuple[Path, ...], *, target: Path, name: str) -> None:
    for path in paths:
        try:
            with _lookup_directory(path) as directory:
                # Any other existing definition could shadow or conflict with
                # the exact per-user unit; configuration never adopts it.
                entries = _drop_in_names(name) + ((name,) if path != target else ())
                for entry in entries:
                    try:
                        os.stat(entry, dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    raise _refuse_configuration()
        except FileNotFoundError:
            continue


def _recheck_configuration_directory(directory: int) -> None:
    with _configuration_directory(create=False) as (current, _):
        left, right = os.fstat(directory), os.fstat(current)
        if (left.st_dev, left.st_ino) != (right.st_dev, right.st_ino):
            raise _refuse_configuration()


@contextmanager
def _configuration_lock(directory: int, name: str) -> Generator[None]:
    if sys.platform != "linux":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import fcntl

    descriptor = os.open(
        "." + name + ".configure.lock",
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
        dir_fd=directory,
    )
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != posix_owner_uid()
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_nlink != 1
            or observed.st_size != 0
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        yield
    finally:
        os.close(descriptor)


def _publish_configuration(directory: int, name: str, payload: bytes) -> None:
    temporary = "." + name + "." + uuid4().hex + ".tmp"
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory
    )
    try:
        with os.fdopen(os.dup(descriptor), "wb") as destination:
            destination.write(payload)
            destination.flush()
        os.fsync(descriptor)
        try:
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        except FileExistsError:
            raise _refuse_configuration() from None
    finally:
        os.close(descriptor)
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)


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

    async def _query_properties(self) -> dict[str, str]:
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
        return values

    async def inspect(self) -> RuntimeManagerInspection:
        """Refuse modified fragments, drop-ins, stale manager loads and unknown states."""
        try:
            values = await self._query_properties()
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

    async def _query_unit_paths(self, target: Path) -> tuple[Path, ...]:
        response = await run_manager_command(
            NativeManagerCommand.SYSTEMCTL,
            ("--user", "--no-pager", "--no-ask-password", "show", "--property=UnitPath"),
        )
        if response.returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return _manager_unit_paths(response.output, target)

    def _require_configuration_values(self, values: dict[str, str], target: Path) -> None:
        if values["DropInPaths"] or values["NeedDaemonReload"] != "no":
            raise _refuse_configuration()
        if values["LoadState"] == "not-found":
            if values["FragmentPath"] or values["UnitFileState"] or values["ActiveState"] != "inactive":
                raise _refuse_configuration()
            return
        if (
            values["LoadState"] != "loaded"
            or values["FragmentPath"] != str(target)
            or values["UnitFileState"] not in {"enabled", "disabled"}
        ):
            raise _refuse_configuration()

    async def configure(self, *, login_autostart: bool) -> RuntimeManagerInspection:
        """Provision exact bytes and set explicit autostart without starting a unit.

        Cancellation waits for the owned configuration task to settle. A failed
        native command can leave a published unit or changed autostart policy;
        no rollback, runtime readiness or private authority is implied.

        Args:
            login_autostart: Explicit operator-selected login startup policy.
        """
        if type(login_autostart) is not bool:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return await await_cancellation_complete(
            self._configure(login_autostart=login_autostart), task_name="linux-user-manager-configure"
        )

    async def _configure(self, *, login_autostart: bool) -> RuntimeManagerInspection:
        try:
            target = _native_home() / ".config" / "systemd" / "user" / self._name
            values = await self._query_properties()
            self._require_configuration_values(values, target)
            unit_paths = await self._query_unit_paths(target.parent)
            _require_lookup_policy(unit_paths, target=target.parent, name=self._name)
            expected = self._definition.encode("utf-8")
            try:
                with _configuration_directory(create=False) as (directory, parent):
                    _configuration_layout(directory, parent, self._name)
                    initial = _read_configuration(directory, self._name)
            except FileNotFoundError:
                initial = None
            if initial is not None and initial != expected:
                raise _refuse_configuration()
            if values["LoadState"] == "loaded" and initial is None:
                raise _refuse_configuration()
            with (
                _configuration_directory(create=True) as (directory, parent),
                _configuration_lock(directory, self._name),
            ):
                if parent / self._name != target:
                    raise _refuse_configuration()
                _configuration_layout(directory, parent, self._name)
                actual = _read_configuration(directory, self._name)
                if actual != initial:
                    raise _refuse_configuration()
                if values["LoadState"] == "loaded" and actual is None:
                    raise _refuse_configuration()
                # Repeat native preflight under the exact owned configuration lock.
                values = await self._query_properties()
                self._require_configuration_values(values, target)
                if await self._query_unit_paths(target.parent) != unit_paths:
                    raise _refuse_configuration()
                _require_lookup_policy(unit_paths, target=parent, name=self._name)
                _recheck_configuration_directory(directory)
                _configuration_layout(directory, parent, self._name)
                if _read_configuration(directory, self._name) != actual:
                    raise _refuse_configuration()
                if actual is None:
                    if values["LoadState"] == "loaded":
                        raise _refuse_configuration()
                    _publish_configuration(directory, self._name, expected)
                response = await run_manager_command(
                    NativeManagerCommand.SYSTEMCTL, ("--user", "--no-pager", "--no-ask-password", "daemon-reload")
                )
                if response.returncode != 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                values = await self._query_properties()
                self._require_configuration_values(values, target)
                if await self._query_unit_paths(target.parent) != unit_paths:
                    raise _refuse_configuration()
                _require_lookup_policy(unit_paths, target=parent, name=self._name)
                _recheck_configuration_directory(directory)
                _configuration_layout(directory, parent, self._name)
                if values["LoadState"] != "loaded" or _read_configuration(directory, self._name) != expected:
                    raise _refuse_configuration()
                if (values["UnitFileState"] == "enabled") is not login_autostart:
                    response = await run_manager_command(
                        NativeManagerCommand.SYSTEMCTL,
                        (
                            "--user",
                            "--no-pager",
                            "--no-ask-password",
                            "--no-reload",
                            "enable" if login_autostart else "disable",
                            self._name,
                        ),
                    )
                    if response.returncode != 0:
                        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                    response = await run_manager_command(
                        NativeManagerCommand.SYSTEMCTL, ("--user", "--no-pager", "--no-ask-password", "daemon-reload")
                    )
                    if response.returncode != 0:
                        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                _recheck_configuration_directory(directory)
                _configuration_layout(directory, parent, self._name)
                if _read_configuration(directory, self._name) != expected:
                    raise _refuse_configuration()
                result = await self.inspect()
                if await self._query_unit_paths(target.parent) != unit_paths:
                    raise _refuse_configuration()
                _require_lookup_policy(unit_paths, target=parent, name=self._name)
                _recheck_configuration_directory(directory)
                _configuration_layout(directory, parent, self._name)
                if (
                    not result.available
                    or not result.provisioned
                    or not result.binding_matches
                    or result.login_autostart is not login_autostart
                    or _read_configuration(directory, self._name) != expected
                ):
                    raise _refuse_configuration()
                return result
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

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
