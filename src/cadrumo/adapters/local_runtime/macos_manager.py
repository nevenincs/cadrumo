"""Exact per-user LaunchAgent control, separate from private runtime authority."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import ctypes
import os
import plistlib
import stat
import sys
import time
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
    RuntimeServiceBinding,
)
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from ...core.descriptor_write import write_all
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .macos_process import MacosProcessWatch, read_macos_process
from .manager_commands import NativeManagerCommand, run_manager_command
from .posix import posix_owner_uid, posix_storage_identity
from .service_definitions import macos_agent_plist, runtime_service_arguments, runtime_service_name


class MacosJobObservation(BaseModel):
    """Closed nonsecret job facts emitted by the bounded native inspector."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    loaded: bool
    binding_matches: bool
    login_autostart: bool | None = None
    process_id: int | None = Field(default=None, gt=0, le=2_147_483_647)


def _equal_plist(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict) and isinstance(expected, dict):
        left, right = cast(dict[object, object], actual), cast(dict[object, object], expected)
        return left.keys() == right.keys() and all(_equal_plist(value, right[key]) for key, value in left.items())
    if isinstance(actual, list) and isinstance(expected, list):
        left_items, right_items = cast(list[object], actual), cast(list[object], expected)
        return len(left_items) == len(right_items) and all(
            _equal_plist(left, right) for left, right in zip(left_items, right_items, strict=True)
        )
    return isinstance(actual, (str, int, bool)) and actual == expected


def macos_agent_definition_policy(payload: bytes, binding: RuntimeServiceBinding) -> bool | None:
    """Recognize only the complete canonical definition for either explicit policy.

    Args:
        payload: Bounded owner-protected property-list bytes.
        binding: Exact installed executable, owner and storage-root identity.
    """
    if len(payload) > 64 * 1024:
        return None
    try:
        actual: object = plistlib.loads(payload)
        for enabled in (False, True):
            expected: object = plistlib.loads(macos_agent_plist(binding, login_autostart=enabled))
            if _equal_plist(actual, expected):
                return enabled
    except (ValueError, plistlib.InvalidFileException):
        return None
    return None


_PRINT_SCALARS = frozenset(
    (
        "active count",
        "path",
        "type",
        "state",
        "program",
        "working directory",
        "stdout path",
        "stderr path",
        "domain",
        "umask",
        "asid",
        "minimum runtime",
        "exit timeout",
        "runs",
        "pid",
        "immediate reason",
        "forks",
        "execs",
        "initialized",
        "trampolined",
        "started suspended",
        "proxy started suspended",
        "checked allocations",
        "checked allocations reason",
        "checked allocations flags",
        "last exit code",
        "spawn type",
        "jetsam priority",
        "jetsam memory limit (active)",
        "jetsam memory limit (inactive)",
        "jetsamproperties category",
        "jetsam thread limit",
        "cpumon",
        "properties",
    )
)
_PRINT_BLOCKS = frozenset(
    (
        "arguments",
        "inherited environment",
        "default environment",
        "environment",
        "semaphores",
        "resource coalition",
        "jetsam coalition",
    )
)


def _printed_job_matches(
    text: str, binding: RuntimeServiceBinding, *, definition_path: str, enabled: bool, pid: int | None
) -> bool:
    """Parse the bounded supported native print view without releasing its contents."""
    if len(text.encode("utf-8")) > 64 * 1024 or any(ord(char) < 32 and char not in "\n\t" for char in text):
        return False
    lines = text.splitlines()
    target = f"gui/{binding.os_owner_id}/{runtime_service_name(binding)}"
    if not lines or lines[0] != target + " = {" or lines[-1] != "}":
        return False
    scalars: dict[str, str] = {}
    blocks: dict[str, tuple[str, ...]] = {}
    index = 1
    while index < len(lines) - 1:
        line = lines[index]
        index += 1
        if not line:
            continue
        if not line.startswith("\t") or line.startswith("\t\t"):
            return False
        key, separator, value = line[1:].partition(" = ")
        if not separator or key in scalars or key in blocks:
            return False
        if value != "{":
            if key not in _PRINT_SCALARS:
                return False
            scalars[key] = value
            continue
        if key not in _PRINT_BLOCKS:
            return False
        members: list[str] = []
        while index < len(lines) - 1 and lines[index] != "\t}":
            member = lines[index]
            index += 1
            if not member.startswith("\t\t") or member.startswith("\t\t\t"):
                return False
            members.append(member[2:])
        if index >= len(lines) - 1:
            return False
        index += 1
        blocks[key] = tuple(members)
    expected_scalars = {
        "path": definition_path,
        "type": "LaunchAgent",
        "program": binding.executable,
        "working directory": binding.storage_root,
        "stdout path": "/dev/null",
        "stderr path": "/dev/null",
        "umask": "77",
        "minimum runtime": "60",
        "exit timeout": "25",
        "properties": "runatload" if enabled else "",
    }
    if any(scalars.get(key) != value for key, value in expected_scalars.items()):
        return False
    if blocks.get("arguments") != (binding.executable, *runtime_service_arguments(binding)):
        return False
    domain = scalars.get("domain", "")
    prefix = f"gui/{binding.os_owner_id} ["
    session = domain.removeprefix(prefix).removesuffix("]")
    if not domain.startswith(prefix) or not domain.endswith("]") or not session.isdecimal() or int(session) <= 0:
        return False
    if scalars.get("asid") != session:
        return False
    if pid is None:
        if "pid" in scalars or scalars.get("state") != "not running":
            return False
    elif scalars.get("pid") != str(pid) or scalars.get("state") != "running":
        return False
    if blocks.get("semaphores") != (("successful exit => 0",) if enabled else None):
        return False
    if blocks.get("default environment") != ("PATH => /usr/bin:/bin:/usr/sbin:/sbin",):
        return False
    environment = blocks.get("environment", ())
    expected_environment = {"OSLogRateLimit => 64", "XPC_SERVICE_NAME => " + runtime_service_name(binding)}
    if len(environment) != 2 or set(environment) != expected_environment:
        return False
    inherited = blocks.get("inherited environment", ())
    return len(inherited) <= 1 and all(value.startswith("SSH_AUTH_SOCK => /") for value in inherited)


def project_macos_job(
    document: object,
    binding: RuntimeServiceBinding,
    *,
    persisted_definition: bytes | None = None,
    native_print: str | None = None,
    definition_path: str | None = None,
) -> MacosJobObservation:
    """Correlate independent effective views with the exact owned definition.

    ServiceManagement exports a reduced job dictionary, not the original plist.
    Effective directory, limits and conditional startup policy require the
    supported bounded native print view. Unknown native shapes refuse. Neither
    view proves independently regrouped descendant containment.

    Args:
        document: Native ServiceManagement property-list result.
        binding: Exact installed executable, owner and storage-root identity.
        persisted_definition: Owner-verified complete canonical definition.
        native_print: Bounded local native effective job view, never public output.
        definition_path: Exact anchored owner-controlled installed definition path.
    """
    if document is None:
        return MacosJobObservation(loaded=False, binding_matches=False)
    if not isinstance(document, dict):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    native_values = cast(dict[object, object], document)
    values: dict[str, object] = {}
    for key, value in native_values.items():
        if not isinstance(key, str):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        values[key] = value
    native_pid = values.get("PID")
    if native_pid is not None and (type(native_pid) is not int or not 0 <= native_pid <= 2_147_483_647):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    pid = native_pid
    if "LastExitStatus" in values and type(values["LastExitStatus"]) is not int:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    policy = None
    persisted_policy = (
        None if persisted_definition is None else macos_agent_definition_policy(persisted_definition, binding)
    )
    expected: dict[str, object] = {
        "Label": runtime_service_name(binding),
        "LimitLoadToSessionType": "Aqua",
        "OnDemand": True,
        "Program": binding.executable,
        "ProgramArguments": [binding.executable, *runtime_service_arguments(binding)],
        "StandardErrorPath": "/dev/null",
        "StandardOutPath": "/dev/null",
    }
    definition = {key: value for key, value in values.items() if key not in {"PID", "LastExitStatus"}}
    if (
        _equal_plist(definition, expected)
        and persisted_policy is not None
        and native_print is not None
        and definition_path is not None
        and _printed_job_matches(
            native_print, binding, definition_path=definition_path, enabled=persisted_policy, pid=pid
        )
    ):
        policy = persisted_policy
    return MacosJobObservation(
        loaded=True,
        binding_matches=policy is not None,
        login_autostart=policy,
        process_id=pid or None,
    )


class MacosLaunchdPort(Protocol):
    """Native metadata/configuration/control seam; never a profile admission port."""

    async def job(self, binding: RuntimeServiceBinding) -> MacosJobObservation:
        """Observe the effective job in the verified native GUI user domain.

        Args:
            binding: Exact installed executable, owner and storage-root identity.
        """
        ...

    async def control(self, arguments: tuple[str, ...], *, timeout: float = 5) -> None:
        """Issue a finite exact-target launchctl request without a prompt.

        Args:
            arguments: Fixed native action and exact GUI-user job target.
            timeout: Finite budget for the native control helper.
        """
        ...

    def definition(self, binding: RuntimeServiceBinding) -> bytes | None:
        """Read a bounded owner-protected definition without following symlinks.

        Args:
            binding: Exact installed executable, owner and storage-root identity.
        """
        ...

    def publish(self, binding: RuntimeServiceBinding, payload: bytes, *, expected: bytes | None) -> None:
        """Compare and atomically publish through a held owner-directory handle.

        Args:
            binding: Exact installed executable, owner and storage-root identity.
            payload: Complete canonical property-list definition.
            expected: Previously observed bytes, or confirmed absence.
        """
        ...

    def definition_path(self, binding: RuntimeServiceBinding) -> str:
        """Return the exact verified per-user LaunchAgents target.

        Args:
            binding: Exact installed executable, owner and storage-root identity.
        """
        ...


def _native_job_dictionary(label: str) -> object:
    """Copy public ServiceManagement job metadata with balanced CF ownership."""
    if sys.platform != "darwin":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    owned: list[int] = []
    release = None
    try:
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        sm = ctypes.CDLL("/System/Library/Frameworks/ServiceManagement.framework/ServiceManagement")
        release = cf.CFRelease
        release.argtypes, release.restype = (ctypes.c_void_p,), None
        create = cf.CFStringCreateWithCString
        create.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32)
        create.restype = ctypes.c_void_p
        name = create(None, label.encode("utf-8"), 0x08000100)
        if not isinstance(name, int) or name <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        owned.append(name)
        domain = ctypes.c_void_p.in_dll(sm, "kSMDomainUserLaunchd")
        if not domain.value:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        copy = sm.SMJobCopyDictionary
        copy.argtypes, copy.restype = (ctypes.c_void_p, ctypes.c_void_p), ctypes.c_void_p
        document = copy(domain, name)
        if document is None:
            return None
        if not isinstance(document, int) or document <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        owned.append(document)
        serialize = cf.CFPropertyListCreateData
        serialize.argtypes = (
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p),
        )
        serialize.restype = ctypes.c_void_p
        error = ctypes.c_void_p()
        data = serialize(None, document, 100, 0, ctypes.byref(error))
        if error.value:
            owned.append(error.value)
        if not isinstance(data, int) or data <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        owned.append(data)
        length = cf.CFDataGetLength
        length.argtypes, length.restype = (ctypes.c_void_p,), ctypes.c_long
        count = length(data)
        if not isinstance(count, int) or not 0 < count <= 64 * 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        address = cf.CFDataGetBytePtr
        address.argtypes, address.restype = (ctypes.c_void_p,), ctypes.c_void_p
        buffer = address(data)
        if not isinstance(buffer, int) or buffer <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return plistlib.loads(ctypes.string_at(buffer, count))
    except (AttributeError, OSError, ValueError, plistlib.InvalidFileException):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    finally:
        if release is not None:
            for pointer in reversed(owned):
                release(pointer)


def _native_definition_directory(*, create: bool) -> tuple[int, Path]:
    if sys.platform != "darwin":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pwd

    uid = posix_owner_uid()
    home = Path(pwd.getpwuid(uid).pw_dir)
    if not home.is_absolute() or ".." in home.parts:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    target = home / "Library" / "LaunchAgents"
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for index, part in enumerate(target.parts[1:], start=1):
            try:
                following = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor
                )
            except FileNotFoundError:
                if not create or index < len(home.parts):
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                following = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor
                )
            metadata = os.fstat(following)
            if metadata.st_uid not in (0, uid) or metadata.st_mode & 0o022:
                os.close(following)
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if index >= len(home.parts) - 1 and metadata.st_uid != uid:
                os.close(following)
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            os.close(descriptor)
            descriptor = following
        return descriptor, target
    except BaseException:
        os.close(descriptor)
        raise


def _read_definition(directory: int, name: str) -> bytes | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != posix_owner_uid()
            or metadata.st_mode & 0o022
            or metadata.st_nlink != 1
            or metadata.st_size > 64 * 1024
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        payload = os.read(descriptor, 64 * 1024 + 1)
        if len(payload) > 64 * 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return payload
    finally:
        os.close(descriptor)


class _MacosInspectorProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    async def close(self) -> None:
        if self._process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()
        await asyncio.wait_for(self._process.wait(), timeout=1)


class _MacosJobProcessWatch:
    def __init__(self, watch: MacosProcessWatch) -> None:
        self.watch = watch

    async def close(self) -> None:
        self.watch.close()


class _NativeMacosLaunchd:
    def __init__(self, binding: RuntimeServiceBinding) -> None:
        if sys.platform != "darwin" or binding.os_owner_id != str(posix_owner_uid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if binding.storage_identity != posix_storage_identity(Path(binding.storage_root)):
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        self._binding = binding

    async def job(self, binding: RuntimeServiceBinding) -> MacosJobObservation:
        owner = await run_manager_command(NativeManagerCommand.LAUNCHCTL, ("manageruid",))
        domain = await run_manager_command(NativeManagerCommand.LAUNCHCTL, ("managername",))
        if owner.returncode or domain.returncode or owner.output.strip() != binding.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if domain.output.strip() != "Aqua":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        owned: list[asyncio.subprocess.Process] = []

        async def launch() -> None:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-m",
                "cadrumo.adapters.local_runtime.macos_manager",
                "--inspect-binding",
                binding.model_dump_json(),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"},
                close_fds=True,
                start_new_session=True,
            )
            owned.append(process)

        try:
            await await_cancellation_complete(launch(), task_name="macos-job-inspector-launch")
            if not owned:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            process = owned[0]
            stdout = process.stdout
            if stdout is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            async with asyncio.timeout(5):
                payload = bytearray()
                while block := await stdout.read(4096):
                    payload.extend(block)
                    if len(payload) > 4096:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if await process.wait() != 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return MacosJobObservation.model_validate_json(bytes(payload))
        except ValidationError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        finally:
            if owned:
                await close_async_resources(
                    _MacosInspectorProcess(owned[0]),
                    task_name="macos-job-inspector-close",
                    primary_error=sys.exception(),
                )

    async def control(self, arguments: tuple[str, ...], *, timeout: float = 5) -> None:
        if arguments and arguments[0] == "bootout":
            owned: list[_MacosJobProcessWatch] = []
            try:
                async with asyncio.timeout(timeout):
                    await self._stop_job(arguments, deadline=time.monotonic() + timeout, owned=owned)
            except TimeoutError:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
            finally:
                await close_async_resources(
                    *owned, task_name="macos-job-process-watch-close", primary_error=sys.exception()
                )
            return
        reply = await run_manager_command(NativeManagerCommand.LAUNCHCTL, arguments, timeout=timeout)
        if reply.returncode:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    async def _stop_job(
        self, arguments: tuple[str, ...], *, deadline: float, owned: list[_MacosJobProcessWatch]
    ) -> None:
        binding = self._binding
        target = f"gui/{binding.os_owner_id}/{runtime_service_name(binding)}"
        if arguments != ("bootout", target):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        payload = self.definition(binding)
        before = await self.job(binding)
        if not before.loaded:
            return
        policy = None if payload is None else macos_agent_definition_policy(payload, binding)
        if not before.binding_matches or policy is None or before.login_autostart != policy:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        owner: _MacosJobProcessWatch | None = None
        if before.process_id is not None:
            owner = _MacosJobProcessWatch(
                MacosProcessWatch(read_macos_process(before.process_id, expected_owner=binding.os_owner_id))
            )
            owned.append(owner)
        current = await self.job(binding)
        if self.definition(binding) != payload or current != before:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if owner is not None and (
            owner.watch.exited
            or read_macos_process(owner.watch.observation.pid, expected_owner=binding.os_owner_id)
            != owner.watch.observation
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        remaining = remaining_budget(deadline)
        reply = await run_manager_command(NativeManagerCommand.LAUNCHCTL, arguments, timeout=remaining)
        if reply.returncode:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        # Removing a launchd registration does not itself certify exit of
        # the retained process incarnation, nor application settlement.
        while True:
            current = await self.job(binding)
            if self.definition(binding) != payload:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            if current.loaded:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            if owner is None or owner.watch.exited:
                return
            remaining = remaining_budget(deadline)
            await asyncio.sleep(min(0.05, remaining))

    def definition_path(self, binding: RuntimeServiceBinding) -> str:
        try:
            directory, path = _native_definition_directory(create=False)
            os.close(directory)
            return str(path / (runtime_service_name(binding) + ".plist"))
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None

    def definition(self, binding: RuntimeServiceBinding) -> bytes | None:
        try:
            directory, _path = _native_definition_directory(create=False)
        except FileNotFoundError:
            return None
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        try:
            return _read_definition(directory, runtime_service_name(binding) + ".plist")
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        finally:
            os.close(directory)

    def publish(self, binding: RuntimeServiceBinding, payload: bytes, *, expected: bytes | None) -> None:
        import fcntl

        if macos_agent_definition_policy(payload, binding) is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            directory, _path = _native_definition_directory(create=True)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        name = runtime_service_name(binding) + ".plist"
        temporary = name + "." + uuid4().hex
        descriptors: list[int] = []
        created = False
        try:
            lock = os.open(
                name + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory
            )
            descriptors.append(lock)
            metadata = os.fstat(lock)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != posix_owner_uid() or metadata.st_mode & 0o077:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if _read_definition(directory, name) != expected:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600, dir_fd=directory
            )
            descriptors.append(descriptor)
            created = True
            write_all(descriptor, payload)
            os.fsync(descriptor)
            os.rename(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            created = False
            os.fsync(directory)
            if _read_definition(directory, name) != payload:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        finally:
            try:
                if created:
                    os.unlink(temporary, dir_fd=directory)
            finally:
                for descriptor in reversed(descriptors):
                    os.close(descriptor)
                os.close(directory)


class MacosUserManager:
    """Control exact GUI-user provisioning without conferring unattended authority."""

    def __init__(self, binding: RuntimeServiceBinding, *, native: MacosLaunchdPort | None = None) -> None:
        """Bind installed identity; an injected native port supplies only OS facts.

        Args:
            binding: Exact installed executable, owner and storage-root identity.
            native: Owning native metadata and control adapter, when supplied.
        """
        self._binding = binding
        self._native = native if native is not None else _NativeMacosLaunchd(binding)
        self._target = f"gui/{binding.os_owner_id}/{runtime_service_name(binding)}"

    async def _facts(self) -> tuple[bytes | None, bool | None, MacosJobObservation]:
        payload = self._native.definition(self._binding)
        policy = None if payload is None else macos_agent_definition_policy(payload, self._binding)
        job = await self._native.job(self._binding)
        if self._native.definition(self._binding) != payload:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if payload is not None and policy is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if job.loaded and (not job.binding_matches or job.login_autostart != policy):
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        return payload, policy, job

    async def inspect(self) -> RuntimeManagerInspection:
        """Observe exact persisted/effective binding; never infer authenticated readiness."""
        try:
            payload, policy, job = await self._facts()
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.UNAVAILABLE:
                raise
            return RuntimeManagerInspection(
                kind=RuntimeManagerKind.MACOS_AGENT,
                available=False,
                provisioned=False,
                binding_matches=False,
                login_autostart=False,
                process_state=RuntimeManagerProcessState.UNKNOWN,
            )
        return RuntimeManagerInspection(
            kind=RuntimeManagerKind.MACOS_AGENT,
            available=True,
            provisioned=payload is not None,
            binding_matches=policy is not None,
            login_autostart=policy is True,
            process_state=RuntimeManagerProcessState.RUNNING
            if job.process_id is not None
            else RuntimeManagerProcessState.STOPPED,
        )

    async def start(self) -> None:
        """Start only existing verified provisioning, retaining its autostart policy."""
        payload, _policy, job = await self._facts()
        if payload is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if not job.loaded:
            await self._native.control(
                ("bootstrap", f"gui/{self._binding.os_owner_id}", self._native.definition_path(self._binding))
            )
            _payload, _policy, job = await self._facts()
            if not job.loaded:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if job.process_id is None:
            await self._native.control(("kickstart", self._target))

    async def stop(self) -> None:
        """Boot out only the verified job; preserve the file's login-start policy.

        The finite native stop permits canonical drain before launchd termination.
        Successful control is not an application settlement or custody receipt.
        """
        _payload, _policy, job = await self._facts()
        if job.loaded:
            await self._native.control(("bootout", self._target), timeout=25)

    async def configure(self, *, login_autostart: bool) -> RuntimeManagerInspection:
        """Publish explicit policy without silently restarting a loaded differing job.

        Args:
            login_autostart: Explicit human-selected launch-at-login policy.
        """
        payload, policy, job = await self._facts()
        if job.loaded and policy != login_autostart:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        proposed = macos_agent_plist(self._binding, login_autostart=login_autostart)
        if payload != proposed:
            self._native.publish(self._binding, proposed, expected=payload)
        if not job.loaded:
            await self._native.control(
                ("bootstrap", f"gui/{self._binding.os_owner_id}", self._native.definition_path(self._binding))
            )
        return await self.inspect()


async def _inspect_macos_job(binding: RuntimeServiceBinding) -> MacosJobObservation:
    """Correlate fresh native views within the outer inspector's five-second bound."""
    native = _NativeMacosLaunchd(binding)
    definition = native.definition(binding)
    label = runtime_service_name(binding)
    target = f"gui/{binding.os_owner_id}/{label}"
    deadline = time.monotonic() + 3.5
    pending_pid: int | None = None
    while True:
        before = _native_job_dictionary(label)
        if before is None:
            if native.definition(binding) != definition:
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            return MacosJobObservation(loaded=False, binding_matches=False)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        printed = await run_manager_command(NativeManagerCommand.LAUNCHCTL, ("print", target), timeout=remaining)
        after = _native_job_dictionary(label)
        if native.definition(binding) != definition:
            raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
        if printed.returncode == 0 and _equal_plist(before, after):
            observed = project_macos_job(
                after,
                binding,
                persisted_definition=definition,
                native_print=printed.output,
                definition_path=native.definition_path(binding),
            )
            if not observed.binding_matches or observed.process_id is None:
                return observed
            if pending_pid is not None and pending_pid != observed.process_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            pending_pid = observed.process_id
            try:
                first = read_macos_process(observed.process_id, expected_owner=binding.os_owner_id)
                second = read_macos_process(observed.process_id, expected_owner=binding.os_owner_id)
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.UNAVAILABLE:
                    raise
            else:
                if first != second:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                if _equal_plist(after, _native_job_dictionary(label)) and native.definition(binding) == definition:
                    return observed
        if time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        await asyncio.sleep(0.05)


def run_macos_job_inspector(arguments: list[str] | None = None) -> int:
    """Inspect framework metadata in a disposable bounded nonsecret helper.

    Args:
        arguments: Exact inspector arguments; defaults to its process arguments.
    """
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--inspect-binding", required=True)
    options = parser.parse_args(arguments)
    if sys.platform != "darwin" or not sys.flags.isolated:
        return 2
    try:
        binding = RuntimeServiceBinding.model_validate_json(options.inspect_binding)
        if binding.os_owner_id != str(posix_owner_uid()):
            return 2
        projected = asyncio.run(_inspect_macos_job(binding))
    except (RuntimeRefusalError, ValueError):
        return 2
    # Only the closed matching/PID/policy projection crosses the helper pipe.
    sys.stdout.write(projected.model_dump_json() + "\n")
    return 0


__all__ = [
    "MacosJobObservation",
    "MacosLaunchdPort",
    "MacosUserManager",
    "macos_agent_definition_policy",
    "project_macos_job",
    "run_macos_job_inspector",
]


if __name__ == "__main__":
    raise SystemExit(run_macos_job_inspector())
