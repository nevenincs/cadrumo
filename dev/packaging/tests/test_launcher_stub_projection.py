"""The Windows launcher projection elides the payload and nothing else.

``assert_installed_console_entry_point`` compares an installed console launcher
against its sibling to prove the installer-fixed stub has not drifted. On
Windows that comparison cannot be made over raw bytes: the launcher carries its
script's zip as a resource, so the resource section and the two header fields
stating its size track the compressed script's length. Two genuine launchers
therefore differ there whenever their scripts differ in length, and the raw
comparison was failing on correct installs -- it compared the payload while
claiming to compare the stub.

:func:`_launcher_stub_projection` fixes that by eliding exactly those bytes. The
elision is only safe because the payload is pinned separately and first: the
caller opens the launcher as a zip and requires a single ``__main__.py`` equal
byte-for-byte to a script it constructs itself, before any projection runs. So
the projected bytes are the ones the script cannot influence, and the script is
checked exactly.

That makes this a loosened security comparison, which is the kind that has to
prove it still discriminates. A projection that elided too much would pass every
input, and the suite would look identical to one that works. So the cases below
assert both directions: two genuine launchers that raw-compare UNEQUAL must
project equal, and a byte changed outside the elided range must still break the
projection.

Windows-only by nature -- the POSIX branch compares a plain-text script and has
no stub -- and skipped rather than faked elsewhere, because a synthesised
portable executable would prove the parser reads a fixture, not that it reads a
launcher this project actually installs.
"""

from __future__ import annotations

import shutil
import struct
import sys
from pathlib import Path

import pytest

from .._installed_wheel_binding import _launcher_stub_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A byte inside the DOS stub, which sits ahead of the portable-executable
#: header and is therefore never inside the resource section this elides. Any
#: offset outside the elided range would serve; this one is stable across every
#: launcher the installer emits.
_DOS_STUB_OFFSET = 0x40


def _launcher(name: str) -> Path:
    resolved = shutil.which(name)
    if resolved is None:
        pytest.skip(f"{name} is not installed in this environment")
    return Path(resolved).resolve(strict=True)


@pytest.fixture(scope="module")
def launchers() -> tuple[bytes, bytes]:
    """The two console launchers this project installs, as raw bytes."""
    if sys.platform != "win32":
        pytest.skip("console launcher stubs exist only on Windows")
    return _launcher("aeat.exe").read_bytes(), _launcher("cadrumo-mcp.exe").read_bytes()


def test_two_genuine_launchers_differ_raw(launchers: tuple[bytes, bytes]) -> None:
    """The premise of the fix, asserted rather than assumed.

    If these were byte-equal the projection would be unnecessary, and every
    other case here would pass for the wrong reason.
    """
    first, second = launchers

    assert first != second, "the two launchers are byte-identical, so this gate proves nothing about the elision"


def test_two_genuine_launchers_project_equal(launchers: tuple[bytes, bytes]) -> None:
    """The failure this fixes: a correct install reported as stub drift."""
    first, second = launchers

    assert _launcher_stub_projection(first) == _launcher_stub_projection(second)


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


def test_a_launcher_that_is_not_a_portable_executable_is_refused() -> None:
    """A malformed input fails loudly rather than projecting to something.

    Runs on every platform: it needs no installed launcher, and the refusal is
    the branch a truncated or substituted file would take.
    """
    with pytest.raises(RuntimeError, match="not a portable executable"):
        _launcher_stub_projection(b"MZ" + b"\0" * 0x3C + struct.pack("<I", 0x40) + b"\0" * 0x40)
