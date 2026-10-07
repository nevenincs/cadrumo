"""File diagnostics count real attempts and independent native event samples."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from .. import runtime_file_access
from ..runtime_file_access import FileOpenTrace, summarize_file_events

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_real_repeated_reads_failed_open_and_write_are_attributed_without_contents(tmp_path: Path) -> None:
    source = tmp_path / "sample.json"
    source.write_text("private-synthetic-content", encoding="utf-8")
    trace = FileOpenTrace()
    with trace:
        assert source.read_text(encoding="utf-8") == "private-synthetic-content"
        assert source.read_bytes() == b"private-synthetic-content"
        with pytest.raises(FileNotFoundError):
            (tmp_path / "missing.json").read_bytes()
        (tmp_path / "output.txt").write_text("never-report-this-content", encoding="utf-8")
    report = trace.report()
    encoded = json.dumps(report)
    assert "private-synthetic-content" not in encoded
    assert "never-report-this-content" not in encoded
    assert source.read_bytes() == b"private-synthetic-content"
    assert trace.report() == report
    rows = report["opens"]
    assert isinstance(rows, list)
    assert sum(row["attempts"] for row in rows) == 4
    assert sum(row["attempts"] for row in rows if row["readable"]) == 3
    assert all(any("test_runtime_file_access" in caller for caller in row["callers"]) for row in rows)


def test_native_events_keep_read_lengths_failures_extensions_and_pids_separate() -> None:
    def event(
        operation: str, result: str, detail: str = "", *, pid: int = 42, path: str = r"C:\app\store.sqlite3"
    ) -> dict[str, str]:
        return {"PID": str(pid), "Operation": operation, "Result": result, "Detail": detail, "Path": path}

    report = summarize_file_events(
        [
            event("ReadFile", "SUCCESS", "Offset: 0, Length: 1,024, Priority: Normal"),
            event("ReadFile", "SUCCESS", "Offset: 1024, Length: 512"),
            event("ReadFile", "END OF FILE", "Offset: 1536, Length: 4,096"),
            event("CreateFile", "SUCCESS"),
            event("CreateFile", "NAME NOT FOUND"),
            event("ReadFile", "SUCCESS", "Length: 9,999", pid=43),
            event("ReadFile", "SUCCESS", "Length: 10", path=r"C:\app\lib.pyc"),
            event("ReadFile", "SUCCESS", "Length: 1.024", path=r"C:\app\lib.pyc"),
            event("RegOpenKey", "SUCCESS"),
            event("ReadFile", "SUCCESS", "Length: 12", path=r"\Device\NamedPipe\runtime"),
        ],
        pids={42},
    )
    types = report["file_types"]
    assert isinstance(types, dict)
    assert types[".sqlite3"]["reported_read_bytes"] == 1536
    assert types[".sqlite3"]["ReadFile"] == 3
    assert types[".sqlite3"]["successful_reads"] == 2
    assert types[".sqlite3"]["successful_opens"] == 1
    assert types[".sqlite3"]["unsuccessful_opens"] == 1
    assert types[".sqlite3"]["unique_paths"] == 1
    assert types[".pyc"]["reported_read_bytes"] == 1034
    assert types["<pipe>"]["reported_read_bytes"] == 12
    operations = report["operations"]
    assert isinstance(operations, dict)
    assert "RegOpenKey" not in operations


def test_successful_native_read_without_length_refuses_a_misleading_report() -> None:
    with pytest.raises(ValueError, match="reported length"):
        summarize_file_events(
            [{"PID": "42", "Operation": "ReadFile", "Result": "SUCCESS", "Detail": "", "Path": "C:\\app\\lib.pyc"}],
            pids={42},
        )


def test_reusing_the_observer_does_not_double_count_hooks(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_bytes(b"sample")
    trace = FileOpenTrace()
    for _ in range(2):
        with trace:
            assert source.read_bytes() == b"sample"
            with pytest.raises(RuntimeError, match="already active"), trace:
                pass
    rows = trace.report()["opens"]
    assert isinstance(rows, list)
    assert sum(row["attempts"] for row in rows) == 2


def test_exit_text_is_not_retained_in_a_failed_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "report.json"
    private_text = "private-synthetic-exit-text"

    def refuse(_name: str, _arguments: list[str]) -> dict[str, object]:
        raise SystemExit(private_text)

    monkeypatch.setattr(runtime_file_access, "_scenario", refuse)
    monkeypatch.setattr(sys, "argv", ["probe", "record", "--scenario", "registry", "--output", str(output)])
    with pytest.raises(SystemExit):
        runtime_file_access.main()
    raw = output.read_text(encoding="utf-8")
    assert private_text not in raw
    assert json.loads(raw)["outcome"] == "SystemExit"
