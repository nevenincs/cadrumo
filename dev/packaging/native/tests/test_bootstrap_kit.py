"""Portable kit publication retains verified bytes and rejects changed sources."""

from pathlib import Path

import pytest

from ..hashing import digest
from ..windows_msi_build import _deliver_kit

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_delivery_keeps_identical_artifacts_and_publishes_descriptor_last(tmp_path: Path) -> None:
    source = tmp_path / "runner.exe"
    source.write_bytes(b"fixture runner bytes")
    directory = tmp_path / "services"
    directory.mkdir()
    descriptor = directory / "kit.json"
    sources = {source.name: (source, digest(source))}
    assert _deliver_kit(directory, descriptor, sources, "verified descriptor\n") == descriptor
    delivered = directory / source.name
    assert delivered.read_bytes() == source.read_bytes()
    _deliver_kit(directory, descriptor, sources, "next descriptor\n")
    assert delivered.read_bytes() == source.read_bytes()
    assert descriptor.read_text(encoding="utf-8") == "next descriptor\n"
    assert sorted(path.name for path in directory.iterdir()) == ["kit.json", "runner.exe"]


def test_changed_source_preserves_last_descriptor_and_cleans_work(tmp_path: Path) -> None:
    source = tmp_path / "version.msi"
    source.write_bytes(b"admitted artifact")
    checksum = digest(source)
    source.write_bytes(b"changed artifact")
    directory = tmp_path / "services"
    directory.mkdir()
    descriptor = directory / "kit.json"
    descriptor.write_text("previous descriptor", encoding="utf-8")
    with pytest.raises(ValueError, match="source changed"):
        _deliver_kit(directory, descriptor, {source.name: (source, checksum)}, "replacement descriptor")
    assert descriptor.read_text(encoding="utf-8") == "previous descriptor"
    assert [path.name for path in directory.iterdir()] == ["kit.json"]


@pytest.mark.windows_only
def test_public_kit_publication_repairs_private_acl_and_allows_native_standard_read(tmp_path: Path) -> None:
    """Exercise real Windows inheritance and restricted-token reads, without installing."""
    import win32api
    import win32con
    import win32security

    from ..package_launch_smoke import _require_public_kit_file

    directory = tmp_path / "services"
    directory.mkdir()
    public = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICI;GRGX;;;BU)", 1
    )
    win32security.SetFileSecurity(
        str(directory),
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        public,
    )
    original = tmp_path / "input.bin"
    contents = b"verified public installation artifact"
    original.write_bytes(contents)
    sources = {name: (original, digest(original)) for name in ("runner.exe", "user.msi", "machine.msi")}
    descriptor = directory / "kit.json"
    restricted_acl = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        "D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;OW)", 1
    )
    for name in (*sources, descriptor.name):
        path = directory / name
        path.write_bytes(original.read_bytes())
        win32security.SetFileSecurity(
            str(path),
            win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            restricted_acl,
        )
        with pytest.raises(AssertionError, match="private temporary ACL"):
            _require_public_kit_file(path)
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_ALL_ACCESS)
    users = win32security.CreateWellKnownSid(win32security.WinBuiltinUsersSid, None)
    administrators = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid, None)
    # The native API accepts SID_AND_ATTRIBUTES pairs; installed stubs model them nominally.
    filtered = win32security.CreateRestrictedToken(token, 1, ((administrators, 0),), (), ((users, 0),))  # ty: ignore[invalid-argument-type]
    try:
        win32security.ImpersonateLoggedOnUser(filtered)
        try:
            with pytest.raises(PermissionError):
                descriptor.read_bytes()
        finally:
            win32security.RevertToSelf()
        _deliver_kit(directory, descriptor, sources, '{"schema":1}\n')
        for name in (*sources, descriptor.name):
            path = directory / name
            _require_public_kit_file(path)
            security = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
            assert not security.GetSecurityDescriptorControl()[0] & win32security.SE_DACL_PROTECTED
            assert any(
                security.GetSecurityDescriptorDacl().GetAce(index)[2] == users
                for index in range(security.GetSecurityDescriptorDacl().GetAceCount())
            )
        win32security.ImpersonateLoggedOnUser(filtered)
        try:
            assert descriptor.read_text(encoding="utf-8") == '{"schema":1}\n'
            for name in sources:
                assert (directory / name).read_bytes() == contents
        finally:
            win32security.RevertToSelf()
        assert sorted(path.name for path in directory.iterdir()) == sorted((*sources, descriptor.name))
    finally:
        win32api.CloseHandle(filtered)
        win32api.CloseHandle(token)
