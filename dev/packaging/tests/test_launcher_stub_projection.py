"""The Windows launcher projection elides the payload and nothing else.

``assert_installed_console_entry_point`` compares an installed console launcher
against its sibling to prove the installer-fixed stub has not drifted. On
Windows, UV stores each console script as a named PE resource. Different script
lengths shift later resources and update the resource-directory and section
sizes, so raw launcher bytes differ even when both fixed stubs are sound.

:func:`_launcher_stub_projection` parses the UV resource tree, drops only the
``UV_SCRIPT_DATA`` value, and retains every other resource value and directory
field. It compares all PE bytes outside the final resource section and refuses
nonzero or unreferenced section padding. The caller pins both launchers' script
ZIPs byte-for-byte to their expected entry points before either projection is
compared.

That makes this a loosened security comparison, which is the kind that has to
prove it still discriminates. A projection that elided too much would pass every
input, and the suite would look identical to one that works. So the cases below
assert both directions: two genuine launchers that raw-compare UNEQUAL must
project equal, while changed UV interpreter-resource, PE-code, and COFF-header
bytes must still break the projection.

Windows-only by nature -- the POSIX branch compares a plain-text script and has
no stub -- and skipped rather than faked elsewhere, because a synthesised
portable executable would prove the parser reads a fixture, not that it reads a
launcher this project actually installs.
"""

from __future__ import annotations

import shutil
import struct
from pathlib import Path

import pytest

from ..installed_wheel_binding import _launcher_stub_projection, installed_python_for_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A byte inside the DOS stub, which sits ahead of the portable-executable
#: header and is therefore never inside the resource section this elides. Any
#: offset outside the elided range would serve; this one is stable across every
#: launcher the installer emits.
_DOS_STUB_OFFSET = 0x40


def _launcher(name: str) -> Path:
    resolved = shutil.which(name)
    if resolved is None:
        pytest.fail(f"{name} is not on PATH; this project installs it as a console script")
    return Path(resolved).resolve(strict=True)


def _section_raw_offset(image: bytes, expected_name: bytes) -> int:
    signature = struct.unpack_from("<I", image, 0x3C)[0]
    section_count = struct.unpack_from("<H", image, signature + 6)[0]
    optional_size = struct.unpack_from("<H", image, signature + 20)[0]
    table = signature + 24 + optional_size
    for index in range(section_count):
        header = table + index * 40
        if image[header : header + 8].rstrip(b"\0") == expected_name:
            offset = struct.unpack_from("<I", image, header + 20)[0]
            assert isinstance(offset, int)
            return offset
    pytest.fail(f"launcher does not contain the {expected_name!r} section")


@pytest.fixture(scope="module")
def launchers() -> tuple[bytes, bytes]:
    """The two console launchers this project installs, as raw bytes.

    No platform guard here: the tests that request this fixture carry
    ``windows_only``, which every lane excludes, so on a POSIX checkout they are
    never selected rather than selected-and-skipped. If one is reached anyway,
    `_launcher` fails loudly rather than reporting green for a stub it never saw.
    """
    return _launcher("aeat.exe").read_bytes(), _launcher("cadrumo-mcp.exe").read_bytes()


@pytest.mark.windows_only
def test_two_genuine_launchers_differ_raw(launchers: tuple[bytes, bytes]) -> None:
    """The premise of the fix, asserted rather than assumed.

    If these were byte-equal the projection would be unnecessary, and every
    other case here would pass for the wrong reason.
    """
    first, second = launchers

    assert first != second, "the two launchers are byte-identical, so this gate proves nothing about the elision"


@pytest.mark.windows_only
def test_two_genuine_launchers_project_equal(launchers: tuple[bytes, bytes]) -> None:
    """The failure this fixes: a correct install reported as stub drift."""
    first, second = launchers

    assert _launcher_stub_projection(first) == _launcher_stub_projection(second)


@pytest.mark.windows_only
def test_a_byte_changed_outside_the_elision_still_breaks_the_projection(
    launchers: tuple[bytes, bytes],
) -> None:
    """Teeth. A projection that elided too much would pass everything.

    This is the case that separates a working elision from a vacuous one, and
    it is the whole reason a loosened comparison needs a test at all.
    """
    first, _ = launchers
    tampered = bytearray(first)
    tampered[_DOS_STUB_OFFSET] ^= 0xFF

    assert _launcher_stub_projection(bytes(tampered)) != _launcher_stub_projection(first)


@pytest.mark.windows_only
def test_a_non_script_uv_resource_change_still_breaks_the_projection(launchers: tuple[bytes, bytes]) -> None:
    first, _ = launchers
    interpreter = str(installed_python_for_cli(_launcher("aeat.exe"))).encode("utf-8")
    offset = first.find(interpreter)
    assert offset >= 0, "the UV interpreter-path resource is missing from the installed launcher"
    tampered = bytearray(first)
    tampered[offset] ^= 0xFF

    assert _launcher_stub_projection(bytes(tampered)) != _launcher_stub_projection(first)


@pytest.mark.windows_only
def test_pe_code_changes_still_break_the_projection(launchers: tuple[bytes, bytes]) -> None:
    first, _ = launchers
    tampered = bytearray(first)
    tampered[_section_raw_offset(first, b".text")] ^= 0xFF

    assert _launcher_stub_projection(bytes(tampered)) != _launcher_stub_projection(first)


@pytest.mark.windows_only
def test_pe_header_changes_still_break_the_projection(launchers: tuple[bytes, bytes]) -> None:
    first, _ = launchers
    signature = struct.unpack_from("<I", first, 0x3C)[0]
    tampered = bytearray(first)
    tampered[signature + 4] ^= 0xFF

    assert _launcher_stub_projection(bytes(tampered)) != _launcher_stub_projection(first)


def test_a_launcher_that_is_not_a_portable_executable_is_refused() -> None:
    """A malformed input fails loudly rather than projecting to something.

    Runs on every platform: it needs no installed launcher, and the refusal is
    the branch a truncated or substituted file would take.
    """
    with pytest.raises(RuntimeError, match="not a portable executable"):
        _launcher_stub_projection(b"MZ" + b"\0" * 0x3C + struct.pack("<I", 0x40) + b"\0" * 0x40)
