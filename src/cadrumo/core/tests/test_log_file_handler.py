"""The log file handler tells the desktop's log view about each record it appends."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import override

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


def _windows_user_event(directory: Path, sddl_for_sid: str) -> tuple[int, str]:
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


_FILE_EVENTS = frozenset({"open", "os.mkdir", "_winapi.CreateFile"})
_observed_file_events: list[tuple[str, str]] | None = None


def _record_file_event(event: str, arguments: tuple[object, ...]) -> None:
    if _observed_file_events is not None and event in _FILE_EVENTS and arguments:
        target = arguments[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            _observed_file_events.append((event, os.fsdecode(target)))


sys.addaudithook(_record_file_event)


def _file_events_under(directory: Path, action: Callable[[], None]) -> list[tuple[str, str]]:
    """Return the audited opens and directory creations below ``directory`` while ``action`` runs."""
    global _observed_file_events
    _observed_file_events = []
    try:
        action()
        events = _observed_file_events
    finally:
        _observed_file_events = None
    prefix = os.path.normcase(os.path.abspath(directory))
    return [(event, path) for event, path in events if os.path.normcase(os.path.abspath(path)).startswith(prefix)]


def _record(message: str) -> logging.LogRecord:
    return logging.makeLogRecord({"msg": message, "levelno": logging.INFO})


def test_steady_state_records_open_and_create_nothing(tmp_path: Path) -> None:
    handler = AnnouncingRotatingFileHandler(tmp_path / "diagnostics" / "probe.log", maxBytes=1 << 20, encoding="utf-8")
    try:
        (tmp_path / "diagnostics").mkdir()
        first = _file_events_under(tmp_path, lambda: handler.emit(_record("first record")))

        def emit_fifty() -> None:
            for index in range(50):
                handler.emit(_record(f"record {index:02d}"))

        later = _file_events_under(tmp_path, emit_fifty)
    finally:
        handler.close()
    # The first record opens the sidecar and the log once each.
    assert {path for _event, path in first} == {
        str(tmp_path / "diagnostics" / "probe.log.lock"),
        str(tmp_path / "diagnostics" / "probe.log"),
    }
    assert later == []
    lines = (tmp_path / "diagnostics" / "probe.log").read_text(encoding="utf-8").splitlines()
    assert lines == ["first record", *(f"record {index:02d}" for index in range(50))]


def test_a_retained_writer_appends_to_the_log_another_writer_rotated(tmp_path: Path) -> None:
    target = tmp_path / "shared.log"
    idle = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    rotating = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    try:
        idle.emit(_record("idle before"))
        # Together with the idle writer's record this passes the cap, so this writer rotates first.
        rotating.emit(_record("r" * 88))
        idle.emit(_record("x"))
    finally:
        idle.close()
        rotating.close()
    assert (tmp_path / "shared.log.1").read_text(encoding="utf-8").splitlines() == ["idle before"]
    assert target.read_text(encoding="utf-8").splitlines() == ["r" * 88, "x"]


def test_a_retained_writer_measures_what_other_writers_appended(tmp_path: Path) -> None:
    target = tmp_path / "shared.log"
    idle = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    other = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    try:
        idle.emit(_record("a" * 10))
        for _ in range(3):
            other.emit(_record("b" * 25))
        # Its own stream wrote one short record, but the shared file is near the cap.
        idle.emit(_record("c" * 10))
    finally:
        idle.close()
        other.close()
    assert (tmp_path / "shared.log.1").read_text(encoding="utf-8").splitlines() == ["a" * 10, *(["b" * 25] * 3)]
    assert target.read_text(encoding="utf-8").splitlines() == ["c" * 10]


def test_a_removed_log_directory_is_recreated_for_the_next_record(tmp_path: Path) -> None:
    directory = tmp_path / "diagnostics"
    handler = AnnouncingRotatingFileHandler(directory / "probe.log", maxBytes=1 << 20, encoding="utf-8")
    try:
        handler.emit(_record("before removal"))
        shutil.rmtree(directory)
        handler.emit(_record("after removal"))
    finally:
        handler.close()
    assert (directory / "probe.log").read_text(encoding="utf-8") == "after removal\n"


def _calls_during(functions: tuple[object, ...], action: Callable[[], None]) -> int:
    """Count the calls Python code makes to ``functions`` while ``action`` runs, observing without replacing them."""
    monitoring = sys.monitoring
    tool = next(candidate for candidate in range(6) if monitoring.get_tool(candidate) is None)
    calls = 0

    def observe(_code: object, _offset: int, called: object, _first: object) -> None:
        nonlocal calls
        if any(called is function for function in functions):
            calls += 1

    monitoring.use_tool_id(tool, "log-file-handler-test")
    try:
        monitoring.register_callback(tool, monitoring.events.CALL, observe)
        monitoring.set_events(tool, monitoring.events.CALL)
        try:
            action()
        finally:
            monitoring.set_events(tool, monitoring.events.NO_EVENTS)
            monitoring.register_callback(tool, monitoring.events.CALL, None)
    finally:
        monitoring.free_tool_id(tool)
    return calls


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the open file's own name is read through a Windows query")
def test_steady_state_records_look_no_path_up(tmp_path: Path) -> None:
    handler = AnnouncingRotatingFileHandler(tmp_path / "probe.log", maxBytes=1 << 20, encoding="utf-8")
    try:
        # The first records open both files and confirm once that each path names them.
        for index in range(2):
            handler.emit(_record(f"settling {index}"))

        def emit_fifty() -> None:
            for index in range(50):
                handler.emit(_record(f"record {index:02d}"))

        lookups = _calls_during((os.stat, os.fstat), emit_fifty)
    finally:
        handler.close()
    assert lookups == 0
    assert len((tmp_path / "probe.log").read_text(encoding="utf-8").splitlines()) == 52


def test_a_settled_writer_follows_another_writers_rotation(tmp_path: Path) -> None:
    target = tmp_path / "shared.log"
    settled = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    rotating = AnnouncingRotatingFileHandler(target, maxBytes=100, backupCount=3, encoding="utf-8")
    try:
        for index in range(3):
            settled.emit(_record(f"settled {index}"))
        # Together with the settled writer's records this passes the cap, so this writer rotates.
        rotating.emit(_record("r" * 70))
        for index in range(2):
            settled.emit(_record(f"after {index}"))
    finally:
        settled.close()
        rotating.close()
    assert (tmp_path / "shared.log.1").read_text(encoding="utf-8").splitlines() == [
        f"settled {index}" for index in range(3)
    ]
    assert target.read_text(encoding="utf-8").splitlines() == ["r" * 70, "after 0", "after 1"]


def test_a_settled_writer_recreates_a_removed_log_directory(tmp_path: Path) -> None:
    directory = tmp_path / "diagnostics"
    handler = AnnouncingRotatingFileHandler(directory / "probe.log", maxBytes=1 << 20, encoding="utf-8")
    try:
        for index in range(3):
            handler.emit(_record(f"before removal {index}"))
        shutil.rmtree(directory)
        for index in range(2):
            handler.emit(_record(f"after removal {index}"))
    finally:
        handler.close()
    assert (directory / "probe.log").read_text(encoding="utf-8").splitlines() == [
        "after removal 0",
        "after removal 1",
    ]


class _CountingFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    @override
    def format(self, record: logging.LogRecord) -> str:
        self.calls += 1
        return super().format(record)


def test_each_record_is_formatted_once(tmp_path: Path) -> None:
    formatter = _CountingFormatter()
    handler = AnnouncingRotatingFileHandler(tmp_path / "probe.log", maxBytes=1 << 20, encoding="utf-8")
    handler.setFormatter(formatter)
    try:
        for index in range(10):
            handler.emit(_record(f"record {index}"))
    finally:
        handler.close()
    # A capped log measures each record before the append writes it; both use one formatting.
    assert formatter.calls == 10
    assert len((tmp_path / "probe.log").read_text(encoding="utf-8").splitlines()) == 10
