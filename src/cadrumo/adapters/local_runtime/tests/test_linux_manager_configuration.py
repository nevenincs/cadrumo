"""Exact isolated unit publication and bounded command-seam configuration.

These tests exercise real protected files without starting a native manager or
claiming native autostart acceptance. The command fixture never runs systemctl.
"""

from __future__ import annotations

import asyncio
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeConfigurableUserManager, RuntimeServiceBinding

from .. import linux_manager
from ..linux_manager import LinuxUserManager
from ..manager_commands import ManagerCommandResult, NativeManagerCommand
from ..posix import posix_storage_identity
from ..service_definitions import linux_user_service, runtime_service_name

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux anchored filesystem and owner primitives"),
]


class _ManagerCommands:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.loaded = False
        self.enabled = False
        self.calls: list[tuple[str, ...]] = []
        self.overrides: dict[str, str] = {}
        self.failure: str | None = None
        self.reload_entered: asyncio.Event | None = None
        self.reload_release: asyncio.Event | None = None
        self.unit_paths: tuple[Path, ...] = (path.parent,)
        self.unit_path_output: str | None = None

    async def run(self, tool: NativeManagerCommand, arguments: tuple[str, ...]) -> ManagerCommandResult:
        assert tool is NativeManagerCommand.SYSTEMCTL and tool.value == "/usr/bin/systemctl"
        assert arguments[:3] == ("--user", "--no-pager", "--no-ask-password")
        self.calls.append(arguments)
        if arguments[3] == "show":
            if arguments[-1] == "--property=UnitPath":
                output = "UnitPath=" + " ".join(str(path) for path in self.unit_paths)
                return ManagerCommandResult(0, self.unit_path_output if self.unit_path_output is not None else output)
            values = {
                "LoadState": "loaded" if self.loaded else "not-found",
                "ActiveState": "inactive",
                "FragmentPath": str(self.path) if self.loaded else "",
                "DropInPaths": "",
                "UnitFileState": ("enabled" if self.enabled else "disabled") if self.loaded else "",
                "NeedDaemonReload": "no",
            }
            values.update(self.overrides)
            return ManagerCommandResult(0, "\n".join(f"{name}={value}" for name, value in values.items()))
        verb = next(value for value in arguments[3:] if not value.startswith("--"))
        if verb == self.failure:
            return ManagerCommandResult(1, "")
        if verb == "daemon-reload":
            if self.reload_entered is not None:
                self.reload_entered.set()
            if self.reload_release is not None:
                await self.reload_release.wait()
            self.loaded = self.path.is_file()
        elif verb in ("enable", "disable"):
            assert arguments[-1] == self.path.name and "--no-reload" in arguments
            wants = self.path.parent / "default.target.wants"
            link = wants / self.path.name
            if verb == "enable":
                wants.mkdir(mode=0o700, exist_ok=True)
                link.symlink_to(self.path)
                self.enabled = True
            else:
                link.unlink()
                self.enabled = False
        elif verb == "start":
            assert "--no-block" in arguments
        else:
            raise AssertionError(verb)
        return ManagerCommandResult(0, "")


@dataclass(frozen=True)
class _Subject:
    manager: LinuxUserManager
    binding: RuntimeServiceBinding
    home: Path
    path: Path
    commands: _ManagerCommands


@pytest.fixture
def subject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Subject:
    if sys.platform != "linux":
        pytest.skip("Physical Linux filesystem primitives")
    import pwd

    home = tmp_path / "native-home"
    home.mkdir(mode=0o700)
    root = tmp_path / "profile-root"
    root.mkdir(mode=0o700)
    binding = RuntimeServiceBinding(
        executable="/usr/bin/true",
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version="synthetic-cohort",
    )
    path = home / ".config" / "systemd" / "user" / (runtime_service_name(binding) + ".service")
    commands = _ManagerCommands(path)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(home), pw_uid=uid))
    monkeypatch.setattr(linux_manager, "run_manager_command", commands.run)
    # Ambient deployment directories must never select the publication target.
    monkeypatch.setenv("HOME", str(tmp_path / "untrusted-home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "untrusted-config"))
    return _Subject(LinuxUserManager(binding), binding, home, path, commands)


def _existing(subject: _Subject, *, enabled: bool = False) -> None:
    subject.path.parent.mkdir(mode=0o700, parents=True)
    for path in (subject.home / ".config", subject.home / ".config/systemd", subject.path.parent):
        path.chmod(0o700)
    subject.path.write_bytes(linux_user_service(subject.binding).encode())
    subject.path.chmod(0o600)
    subject.commands.loaded = True
    subject.commands.enabled = enabled
    if enabled:
        wants = subject.path.parent / "default.target.wants"
        wants.mkdir(mode=0o700)
        (wants / subject.path.name).symlink_to(subject.path)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_first_configuration_publishes_exact_private_unit_and_explicit_policy(
    subject: _Subject, enabled: bool
) -> None:
    assert isinstance(subject.manager, RuntimeConfigurableUserManager)
    result = await subject.manager.configure(login_autostart=enabled)
    assert result.available and result.provisioned and result.binding_matches
    assert result.login_autostart is enabled
    assert subject.path.read_bytes() == linux_user_service(subject.binding).encode()
    assert stat.S_IMODE(subject.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(subject.path.parent.stat().st_mode) == 0o700
    assert subject.path.stat().st_nlink == 1
    assert not any(
        value in ("start", "restart", "enable-linger", "--now", "--force")
        for call in subject.commands.calls
        for value in call
    )
    assert not (subject.home.parent / "untrusted-home").exists()
    assert not (subject.home.parent / "untrusted-config").exists()
    assert not list(subject.path.parent.glob("*.tmp"))


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [False, True])
async def test_existing_policy_changes_preserve_unit_inode_and_never_start(subject: _Subject, initial: bool) -> None:
    _existing(subject, enabled=initial)
    before = subject.path.stat()
    result = await subject.manager.configure(login_autostart=not initial)
    assert result.login_autostart is not initial
    after = subject.path.stat()
    assert (before.st_dev, before.st_ino, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_mtime_ns)
    await subject.manager.start()
    assert subject.commands.calls[-1][-2:] == ("start", subject.path.name)
    assert "enable" not in subject.commands.calls[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        {"FragmentPath": "/usr/lib/systemd/user/foreign.service"},
        {"DropInPaths": "/usr/lib/systemd/user/service.d/foreign.conf"},
        {"NeedDaemonReload": "yes"},
        {"LoadState": "masked"},
        {"UnitFileState": "enabled-runtime"},
    ],
)
async def test_loaded_foreign_dropin_or_stale_configuration_refuses_before_mutation(
    subject: _Subject, override: dict[str, str]
) -> None:
    _existing(subject)
    before = subject.path.read_bytes()
    subject.commands.overrides = override
    with pytest.raises(RuntimeRefusalError) as caught:
        await subject.manager.configure(login_autostart=True)
    assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    assert subject.path.read_bytes() == before
    assert len(subject.commands.calls) == 1
    assert not (subject.path.parent / ("." + subject.path.name + ".configure.lock")).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conflict", ["bytes", "symlink", "hardlink", "permissions", "drop-in", "prefix", "type", "wants"]
)
async def test_actual_filesystem_conflicts_are_preserved_before_any_command_mutation(
    subject: _Subject, conflict: str
) -> None:
    _existing(subject)
    if conflict == "bytes":
        subject.path.write_bytes(b"unrelated unit body")
    elif conflict == "symlink":
        original = subject.path.with_suffix(".foreign")
        subject.path.rename(original)
        subject.path.symlink_to(original)
    elif conflict == "hardlink":
        os.link(subject.path, subject.path.with_suffix(".foreign"))
    elif conflict == "permissions":
        subject.path.chmod(0o666)
    elif conflict in ("drop-in", "prefix", "type"):
        name = {"drop-in": subject.path.name + ".d", "prefix": "cadrumo-.service.d", "type": "service.d"}[conflict]
        (subject.path.parent / name).mkdir(mode=0o700)
    else:
        wants = subject.path.parent / "default.target.wants"
        wants.mkdir(mode=0o700)
        (wants / subject.path.name).symlink_to(subject.path.with_suffix(".foreign"))
    before = subject.path.read_bytes()
    with pytest.raises(RuntimeRefusalError):
        await subject.manager.configure(login_autostart=True)
    assert subject.path.read_bytes() == before
    assert all(call[3] == "show" for call in subject.commands.calls)
    assert not (subject.path.parent / ("." + subject.path.name + ".configure.lock")).exists()


@pytest.mark.asyncio
async def test_native_command_failure_preserves_truthful_published_state(subject: _Subject) -> None:
    subject.commands.failure = "daemon-reload"
    with pytest.raises(RuntimeRefusalError) as caught:
        await subject.manager.configure(login_autostart=True)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert subject.path.read_bytes() == linux_user_service(subject.binding).encode()
    assert not subject.commands.enabled
    assert not any("enable" in call for call in subject.commands.calls)


@pytest.mark.asyncio
async def test_cancellation_joins_configuration_without_claiming_rollback(subject: _Subject) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    subject.commands.reload_entered = entered
    subject.commands.reload_release = release
    configuration = asyncio.create_task(subject.manager.configure(login_autostart=True))
    await entered.wait()
    configuration.cancel()
    await asyncio.sleep(0)
    assert not configuration.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await configuration
    assert subject.commands.enabled and subject.path.exists()
    assert subject.path.read_bytes() == linux_user_service(subject.binding).encode()
    # The actual held lock and descriptors are released before cancellation surfaces.
    result = await subject.manager.configure(login_autostart=True)
    assert result.binding_matches and result.login_autostart


def test_publication_never_clobbers_a_concurrent_exact_target(subject: _Subject) -> None:
    _existing(subject)
    before = subject.path.read_bytes()
    with linux_manager._configuration_directory(create=False) as (directory, _):
        with pytest.raises(RuntimeRefusalError) as caught:
            linux_manager._publish_configuration(directory, subject.path.name, b"replacement")
        assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    assert subject.path.read_bytes() == before and subject.path.stat().st_nlink == 1


@pytest.mark.asyncio
async def test_symlinked_configuration_directory_refuses_without_creating_outside_home(subject: _Subject) -> None:
    outside = subject.home.parent / "foreign-directory"
    outside.mkdir(mode=0o700)
    (subject.home / ".config").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeRefusalError):
        await subject.manager.configure(login_autostart=True)
    assert not list(outside.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["unit", "unit-drop-in", "type-drop-in", "prefix-drop-in"])
async def test_missing_unit_refuses_inherited_search_path_conflicts_before_publication(
    subject: _Subject, entry: str
) -> None:
    vendor = subject.home.parent / "isolated-vendor-unit-path"
    vendor.mkdir(mode=0o700)
    subject.commands.unit_paths = (subject.path.parent, vendor)
    names = {
        "unit": subject.path.name,
        "unit-drop-in": subject.path.name + ".d",
        "type-drop-in": "service.d",
        "prefix-drop-in": "cadrumo-runtime-.service.d",
    }
    foreign = vendor / names[entry]
    if entry == "unit":
        foreign.write_bytes(b"foreign definition")
    else:
        foreign.mkdir(mode=0o700)
    with pytest.raises(RuntimeRefusalError) as caught:
        await subject.manager.configure(login_autostart=True)
    assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    assert foreign.exists() and not (subject.home / ".config").exists()
    assert all(call[3] == "show" for call in subject.commands.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output", ["", "UnitPath=relative", "UnitPath=/unrelated", "UnitPath=/escaped\\ path", "UnitPath=/a\n/b"]
)
async def test_missing_or_unsupported_effective_unit_path_refuses_before_filesystem_mutation(
    subject: _Subject, output: str
) -> None:
    subject.commands.unit_path_output = output
    with pytest.raises(RuntimeRefusalError) as caught:
        await subject.manager.configure(login_autostart=False)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert not (subject.home / ".config").exists()
