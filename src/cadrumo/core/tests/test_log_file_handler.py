"""The log file handler tells the desktop's log view about each record it appends."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from ..log_file_handler import AnnouncingRotatingFileHandler, append_signal_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_signal_name_hashes_with_fnv1a_64() -> None:
    # The published FNV-1a 64 test vectors.
    assert append_signal_name("") == "Local\\cadrumo-log-append-cbf29ce484222325"
    assert append_signal_name("a") == "Local\\cadrumo-log-append-af63dc4c8601ec8c"
    assert append_signal_name("foobar") == "Local\\cadrumo-log-append-85944171f73967e8"


def test_spellings_of_one_directory_share_the_name_the_desktop_derives() -> None:
    name = append_signal_name(r"C:\Users\Example\AppData\Local\cadrumo\logs")
    # The desktop's platform crate pins the same name for this directory.
    assert name == r"Local\cadrumo-log-append-c2f24f27d31c8a0a"
    for spelling in (
        r"c:\users\example\appdata\local\cadrumo\logs",
        "C:/Users/Example/AppData/Local/cadrumo/logs",
        "C:\\Users\\Example\\AppData\\Local\\cadrumo\\logs\\",
        r"\\?\C:\Users\Example\AppData\Local\cadrumo\logs",
    ):
        assert append_signal_name(spelling) == name, spelling
    assert append_signal_name(r"C:\Users\Example\AppData\Local\cadrumo-dev\logs") != name


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the append signal is a Windows named event")
def test_each_record_the_handler_appends_sets_its_directory_signal(tmp_path: Path) -> None:
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateEventExW
        create.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32)
        create.restype = ctypes.c_void_p
        wait = kernel.WaitForSingleObject
        wait.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        wait.restype = ctypes.c_uint32
        close = kernel.CloseHandle
        close.argtypes = (ctypes.c_void_p,)
        # As the desktop's reader opens it: manual reset, waitable and resettable.
        reader = create(None, append_signal_name(str(tmp_path)), 0x0001, 0x00100002)
        assert reader, ctypes.get_last_error()
        handler = AnnouncingRotatingFileHandler(tmp_path / "cadrumo.log", encoding="utf-8")
        try:
            assert wait(reader, 0) != 0, "the signal was set before any record"
            handler.emit(logging.makeLogRecord({"msg": "one record", "levelno": logging.INFO}))
            assert wait(reader, 0) == 0, "an appended record did not set the signal"
            assert (tmp_path / "cadrumo.log").read_text(encoding="utf-8") == "one record\n"
        finally:
            handler.close()
            close(reader)
