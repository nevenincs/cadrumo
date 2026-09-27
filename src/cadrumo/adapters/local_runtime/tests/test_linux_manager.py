"""Native systemd parsing and read-only manager checks without installing units."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding

from ..linux_manager import LinuxUserManager, _exact_fragment
from ..posix import posix_storage_identity
from ..service_definitions import linux_user_service, runtime_service_name

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux user systemd"),
]


def _binding(root: Path) -> RuntimeServiceBinding:
    if sys.platform == "win32":
        pytest.skip("requires native POSIX owner identity")
    return RuntimeServiceBinding(
        executable="/usr/bin/true",
        storage_root=str(root),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version="synthetic-cohort",
    )


@pytest.mark.asyncio
async def test_systemd_native_parser_accepts_definition_without_loading_or_starting(tmp_path: Path) -> None:
    if not Path("/usr/bin/systemd-analyze").is_file():
        pytest.skip("systemd-analyze unavailable; native unit parsing remains unproven")
    root = tmp_path / 'literal %n $HOME "quoted"'
    root.mkdir()
    binding = _binding(root)
    unit = tmp_path / (runtime_service_name(binding) + ".service")
    unit.write_text(linux_user_service(binding))
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/systemd-analyze",
        "--user",
        "--man=no",
        "verify",
        str(unit),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        assert process.returncode == 0, stderr.decode(errors="replace")
        assert not stdout, stdout
        assert not stderr, stderr
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), timeout=2)


@pytest.mark.asyncio
async def test_available_manager_does_not_make_a_missing_unit_startable(tmp_path: Path) -> None:
    manager = LinuxUserManager(_binding(tmp_path))
    inspection = await manager.inspect()
    if not inspection.available:
        pytest.skip("user systemd unavailable; native manager control remains unproven")
    assert not inspection.provisioned
    assert not inspection.binding_matches
    assert not inspection.login_autostart
    with pytest.raises(RuntimeRefusalError) as caught:
        await manager.start()
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


def test_fragment_permissions_content_and_symlink_substitution_refuse(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("requires native POSIX file protections")
    unit = tmp_path / "synthetic.service"
    unit.write_text("expected")
    unit.chmod(0o600)
    assert _exact_fragment(str(unit), "expected")
    assert not _exact_fragment(str(unit), "different")
    unit.chmod(0o666)
    assert not _exact_fragment(str(unit), "expected")
    unit.chmod(0o600)
    alias = tmp_path / "alias.service"
    alias.symlink_to(unit)
    assert not _exact_fragment(str(alias), "expected")
