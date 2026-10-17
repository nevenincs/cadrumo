"""The log file handler tells the desktop's log view about each record it appends."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from ..log_file_handler import AnnouncingRotatingFileHandler, _fnv1a, append_signal_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SID = "S-1-5-21-1-2-3-1001"


def test_the_signal_name_hashes_with_fnv1a_64() -> None:
    # The published FNV-1a 64 test vectors.
    assert _fnv1a(b"") == 0xCBF29CE484222325
    assert _fnv1a(b"a") == 0xAF63DC4C8601EC8C
    assert _fnv1a(b"foobar") == 0x85944171F73967E8


def test_spellings_of_one_directory_share_the_name_the_desktop_derives() -> None:
    name = append_signal_name(r"C:\Users\Example\AppData\Local\cadrumo\logs", _SID)
    # The desktop's platform crate pins the same name for this directory and user.
    assert name == r"Local\cadrumo-log-append-S-1-5-21-1-2-3-1001-c2f24f27d31c8a0a"
    for spelling in (
        r"c:\users\example\appdata\local\cadrumo\logs",
        "C:/Users/Example/AppData/Local/cadrumo/logs",
        "C:\\Users\\Example\\AppData\\Local\\cadrumo\\logs\\",
        r"\\?\C:\Users\Example\AppData\Local\cadrumo\logs",
        r"C:\Users\Example\AppData\Local\cadrumo\.\logs",
        r"C:\Users\Example\AppData\Local\cadrumo\tmp\..\logs",
    ):
        assert append_signal_name(spelling, _SID) == name, spelling
    assert append_signal_name(r"C:\Users\Example\AppData\Local\cadrumo-dev\logs", _SID) != name
    assert append_signal_name(r"C:\Users\Example\AppData\Local\cadrumo\logs", "S-1-5-21-1-2-3-1002") != name


def _windows_user_event(directory: Path, sddl_for_sid: str) -> tuple[object, str]:
    """Create the event the desktop's reader would, under ``sddl_for_sid`` formatted with the user's SID."""
    if sys.platform == "win32":
        import pywintypes
        import win32api
        import win32event
        import win32security

        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
        sid = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
        attributes = pywintypes.SECURITY_ATTRIBUTES()
        attributes.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            sddl_for_sid.format(sid=sid), win32security.SDDL_REVISION_1
        )
        return win32event.CreateEvent(attributes, True, False, append_signal_name(str(directory), sid)), sid
    raise AssertionError("the append signal is a Windows fixture")


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the append signal is a Windows named event")
def test_each_record_the_handler_appends_sets_its_directory_signal(tmp_path: Path) -> None:
    if sys.platform == "win32":
        import win32event

        reader, _sid = _windows_user_event(tmp_path, "O:{sid}D:P(A;;GA;;;{sid})")
        handler = AnnouncingRotatingFileHandler(tmp_path / "cadrumo.log", encoding="utf-8")
        try:
            assert win32event.WaitForSingleObject(reader, 0) != win32event.WAIT_OBJECT_0
            handler.emit(logging.makeLogRecord({"msg": "one record", "levelno": logging.INFO}))
            assert win32event.WaitForSingleObject(reader, 0) == win32event.WAIT_OBJECT_0
            assert (tmp_path / "cadrumo.log").read_text(encoding="utf-8") == "one record\n"
        finally:
            handler.close()


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the append signal is a Windows named event")
def test_a_squatted_signal_name_costs_no_record(tmp_path: Path) -> None:
    if sys.platform == "win32":
        import win32event

        # Another holder took the name first and grants this user only SYNCHRONIZE.
        squatter, _sid = _windows_user_event(tmp_path, "D:P(A;;0x00100000;;;{sid})")
        handler = AnnouncingRotatingFileHandler(tmp_path / "cadrumo.log", encoding="utf-8")
        try:
            handler.emit(logging.makeLogRecord({"msg": "one record", "levelno": logging.INFO}))
            assert (tmp_path / "cadrumo.log").read_text(encoding="utf-8") == "one record\n"
            assert win32event.WaitForSingleObject(squatter, 0) != win32event.WAIT_OBJECT_0
        finally:
            handler.close()
