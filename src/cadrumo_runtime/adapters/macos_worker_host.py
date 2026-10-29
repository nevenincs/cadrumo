"""Native launchd and owner-only marker host for macOS workers."""

from __future__ import annotations

import contextlib
import os
import stat
import sys
from pathlib import Path
from typing import Protocol

from cadrumo.core.descriptor_write import write_all
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.posix import open_private_namespace, posix_owner_uid

from .containment_commands import ContainmentCommand, ContainmentCommandResult, run_containment_command_sync
from .macos_coalition import read_macos_resource_coalition, terminate_macos_coalition
from .macos_process import (
    MacosProcessIncarnation,
    MacosProcessObservation,
    MacosProcessWatch,
    read_macos_incarnation,
    read_macos_process,
)
from .macos_worker_markers import MACOS_MARKER_LIMIT, MACOS_MARKER_SUFFIX

_PENDING_SUFFIX = ".pending"
_DEFINITION_SUFFIX = ".plist"


class MacosExitWatch(Protocol):
    """Latched exit observation for one exact process."""

    @property
    def exited(self) -> bool:
        """Whether the watched process has exited."""
        ...

    def wait(self, *, timeout: float) -> bool:
        """Wait a finite budget for exit.

        Args:
            timeout: Finite wait budget in seconds, at most sixty.
        """
        ...

    def close(self) -> None:
        """Release the native observation."""
        ...


class MacosWorkerHost(Protocol):
    """Native launchd, process and marker facts consumed by the worker scope."""

    def owner_uid(self) -> int:
        """Return the native owner UID."""
        ...

    def launchctl(self, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        """Run one bounded launchctl request.

        Args:
            arguments: Exact launchctl action and target.
        """
        ...

    def bootstrap(self, label: str, definition: bytes) -> ContainmentCommandResult:
        """Bootstrap a private definition into the GUI domain, deleting it on every path.

        Args:
            label: Exact job label.
            definition: Complete job property list.
        """
        ...

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        """Read a live PID's exact incarnation; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def coalition(self, pid: int) -> int | None:
        """Read a live PID's resource coalition; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def observe(self, pid: int) -> MacosProcessObservation:
        """Read the owner's live process identity.

        Args:
            pid: Kernel PID.
        """
        ...

    def watch(self, observation: MacosProcessObservation) -> MacosExitWatch:
        """Retain an exit watch for one verified identity.

        Args:
            observation: Exact identity to watch.
        """
        ...

    def terminate_coalition(self, coalition: int, *, deadline: float) -> None:
        """Kill every coalition member until it is proven empty.

        Args:
            coalition: Resource coalition ID.
            deadline: Monotonic deadline.
        """
        ...

    def markers(self, prefix: str) -> dict[str, bytes]:
        """Read marker files whose names start with a storage-scope prefix.

        Args:
            prefix: Storage-scoped label prefix.
        """
        ...

    def publish_marker(self, label: str, payload: bytes) -> None:
        """Durably replace one job's marker.

        Args:
            label: Exact job label.
            payload: Canonical marker encoding.
        """
        ...

    def remove_marker(self, label: str) -> None:
        """Durably remove one job's marker, after any definition its abrupt loss left behind.

        An absent marker or definition is already removed.

        Args:
            label: Exact job label.
        """
        ...


def _private_open_flags(*, nonblocking: bool = False) -> int:
    """Darwin open flags refusing symlinks and keeping descriptors out of children."""
    if sys.platform == "darwin":
        return os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_NONBLOCK if nonblocking else 0)
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)


class NativeMacosWorkerHost:
    """Darwin launchd, libproc and owner-only marker directory."""

    def _directory(self, *, create: bool) -> tuple[Path, int]:
        if sys.platform == "darwin":
            try:
                return open_private_namespace(
                    Path("/").joinpath("tmp", f"cdr-{posix_owner_uid()}-launchd-workers"), create=create
                )
            except RefusalError:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)

    def owner_uid(self) -> int:
        """Return the native owner UID."""
        return posix_owner_uid()

    def launchctl(self, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        """Run one bounded launchctl request."""
        return run_containment_command_sync(ContainmentCommand.LAUNCHCTL, arguments)

    def bootstrap(self, label: str, definition: bytes) -> ContainmentCommandResult:
        """Bootstrap a private definition into the GUI domain, deleting it on every path."""
        directory, descriptor = self._directory(create=True)
        name = label + _DEFINITION_SUFFIX
        try:
            file = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _private_open_flags(), 0o600, dir_fd=descriptor)
            try:
                try:
                    write_all(file, definition)
                finally:
                    os.close(file)
                # launchd keeps the loaded job after its definition file is gone.
                return run_containment_command_sync(
                    ContainmentCommand.LAUNCHCTL, ("bootstrap", f"gui/{posix_owner_uid()}", str(directory / name))
                )
            finally:
                os.unlink(name, dir_fd=descriptor)
        except OSError:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        """Read a live PID's exact incarnation; None when no live process holds it."""
        return read_macos_incarnation(pid)

    def coalition(self, pid: int) -> int | None:
        """Read a live PID's resource coalition; None when no live process holds it."""
        return read_macos_resource_coalition(pid)

    def observe(self, pid: int) -> MacosProcessObservation:
        """Read the owner's live process identity."""
        return read_macos_process(pid, expected_owner=str(posix_owner_uid()))

    def watch(self, observation: MacosProcessObservation) -> MacosExitWatch:
        """Retain an exit watch for one verified identity."""
        return MacosProcessWatch(observation)

    def terminate_coalition(self, coalition: int, *, deadline: float) -> None:
        """Kill every coalition member until it is proven empty."""
        terminate_macos_coalition(coalition, deadline=deadline)

    def _read_marker(self, descriptor: int, name: str) -> bytes:
        file = os.open(name, os.O_RDONLY | _private_open_flags(nonblocking=True), dir_fd=descriptor)
        try:
            metadata = os.fstat(file)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != posix_owner_uid()
                or metadata.st_mode & 0o077
                or metadata.st_nlink != 1
                or metadata.st_size > MACOS_MARKER_LIMIT
            ):
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            return os.read(file, MACOS_MARKER_LIMIT + 1)
        finally:
            os.close(file)

    def markers(self, prefix: str) -> dict[str, bytes]:
        """Read marker files whose names start with a storage-scope prefix."""
        _directory, descriptor = self._directory(create=False)
        if descriptor < 0:
            return {}
        try:
            entries: dict[str, bytes] = {}
            for name in os.listdir(descriptor):
                if not name.startswith(prefix) or not name.endswith(MACOS_MARKER_SUFFIX):
                    continue
                entries[name] = self._read_marker(descriptor, name)
            return entries
        except OSError:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def publish_marker(self, label: str, payload: bytes) -> None:
        """Durably replace one job's marker."""
        _directory, descriptor = self._directory(create=True)
        pending = label + _PENDING_SUFFIX
        try:
            file = os.open(
                pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _private_open_flags(), 0o600, dir_fd=descriptor
            )
            try:
                metadata = os.fstat(file)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != posix_owner_uid()
                    or metadata.st_mode & 0o077
                    or metadata.st_nlink != 1
                ):
                    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
                write_all(file, payload)
                os.fsync(file)
            finally:
                os.close(file)
            os.replace(pending, label + MACOS_MARKER_SUFFIX, src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.fsync(descriptor)
        except OSError:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def remove_marker(self, label: str) -> None:
        """Durably remove one job's marker, after any definition its abrupt loss left behind."""
        _directory, descriptor = self._directory(create=False)
        if descriptor < 0:
            return
        try:
            # A runtime lost inside launchctl bootstrap never deletes its
            # definition. The marker goes last: it is the reaping obligation.
            for name in (label + _DEFINITION_SUFFIX, label + _PENDING_SUFFIX, label + MACOS_MARKER_SUFFIX):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(name, dir_fd=descriptor)
            os.fsync(descriptor)
        except OSError:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)
