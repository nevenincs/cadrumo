"""The component records the native engine writes, read and located the way Python consumers use them.

``_component_records/browser.json`` is the record the engine writes for a
browser install, produced and checked by the engine's own test, with the storage
root left as a placeholder. Reading it here proves the two languages agree on
the record's shape and on where the browser and its record live.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ..component_records import (
    ComponentItem,
    ComponentLocateOutcome,
    ComponentRecordState,
    component_records_root,
    locate_component,
    read_component_record,
)
from ..config import Settings
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURE = Path(__file__).parent / "_component_records" / "browser.json"
_PLACEHOLDER = "<storage-root>"
_DRIVER = "1.64.0-beta-1791568591000"


def _engine_record(storage_root: Path) -> dict[str, Any]:
    text = _FIXTURE.read_text(encoding="utf-8").replace(_PLACEHOLDER, storage_root.as_posix())
    loaded: object = json.loads(text)
    assert isinstance(loaded, dict)
    return loaded


def _install(storage_root: Path, record: dict[str, Any] | None = None) -> Path:
    """Write the engine's record where the engine writes it, and the executables it names."""
    record = _engine_record(storage_root) if record is None else record
    records_root = component_records_root(Settings(cadrumo_local_storage_root=storage_root))
    records_root.mkdir(parents=True, exist_ok=True)
    (records_root / "browser.json").write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
    location = record["location"]
    assert isinstance(location, dict)
    folder = Path(location["root"])
    for relative in location["paths"].values():
        executable = folder / relative
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(b"executable")
    return records_root


def test_the_record_the_engine_writes_reads_and_locates_the_browser_where_python_looks(tmp_path: Path) -> None:
    records_root = _install(tmp_path)

    assert records_root == tmp_path / "components" / "receipts"
    reading = read_component_record(ComponentItem.BROWSER, records_root=records_root)
    assert reading.state is ComponentRecordState.PRESENT
    record = reading.record
    assert record is not None
    assert record.version == "156.0.8078.4"
    assert record.hosts == ("cdn.playwright.dev",)
    assert record.verified_at.isoformat() == "2026-10-24T13:00:00+00:00"
    assert [entry.path for entry in record.files] == sorted(entry.path for entry in record.files)
    assert record.location is not None
    browsers = tmp_path / storage_location(StorageCategory.PLAYWRIGHT_BROWSERS).relative_path()
    assert record.location.folder == browsers

    located = locate_component(
        ComponentItem.BROWSER,
        records_root=records_root,
        expected_folder=browsers,
        expected_facts={"playwright_driver": _DRIVER},
    )
    assert located.located
    assert located.version == "156.0.8078.4"
    assert located.folder == browsers
    assert set(located.paths) == {"chromium", "chromium-headless-shell"}
    assert located.paths["chromium"] == browsers / "chromium-1248" / "chrome-win64" / "chrome.exe"


def test_a_record_for_another_folder_driver_or_with_a_path_gone_does_not_locate(tmp_path: Path) -> None:
    records_root = _install(tmp_path)
    browsers = tmp_path / "components" / "playwright"

    elsewhere = locate_component(ComponentItem.BROWSER, records_root=records_root, expected_folder=tmp_path / "other")
    assert elsewhere.outcome is ComponentLocateOutcome.OTHER_FOLDER
    upgraded = locate_component(
        ComponentItem.BROWSER, records_root=records_root, expected_facts={"playwright_driver": "1.65.0"}
    )
    assert upgraded.outcome is ComponentLocateOutcome.OTHER_IDENTITY

    headless = browsers / "chromium_headless_shell-1248" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe"
    headless.unlink()
    missing = locate_component(ComponentItem.BROWSER, records_root=records_root, expected_folder=browsers)
    assert missing.outcome is ComponentLocateOutcome.PATH_MISSING
    assert missing.missing == ("chromium-headless-shell",)
    assert not missing.located


def test_no_record_and_a_record_without_a_location_never_locate(tmp_path: Path) -> None:
    records_root = tmp_path / "components" / "receipts"
    assert read_component_record(ComponentItem.BROWSER, records_root=records_root).state is ComponentRecordState.ABSENT
    assert (
        locate_component(ComponentItem.BROWSER, records_root=records_root).outcome is ComponentLocateOutcome.NO_RECORD
    )

    record = _engine_record(tmp_path)
    _install(tmp_path, record)
    del record["location"]
    (records_root / "browser.json").write_text(json.dumps(record), encoding="utf-8")
    assert read_component_record(ComponentItem.BROWSER, records_root=records_root).state is ComponentRecordState.PRESENT
    no_location = locate_component(ComponentItem.BROWSER, records_root=records_root)
    assert no_location.outcome is ComponentLocateOutcome.NO_LOCATION
    assert no_location.version == "156.0.8078.4"


@pytest.mark.parametrize(
    "damage",
    ["not json", "foreign item", "relative folder", "escaping path", "unknown field", "oversized"],
)
def test_a_damaged_or_foreign_record_reads_unreadable_rather_than_absent(tmp_path: Path, damage: str) -> None:
    record = _engine_record(tmp_path)
    records_root = _install(tmp_path, record)
    target = records_root / "browser.json"
    location = record["location"]
    assert isinstance(location, dict)
    if damage == "not json":
        target.write_bytes(b"{not json")
    elif damage == "foreign item":
        target.unlink()
        target = records_root / "local_ai.json"
        target.write_text(json.dumps(record), encoding="utf-8")
    elif damage == "relative folder":
        location["root"] = "components/playwright"
        target.write_text(json.dumps(record), encoding="utf-8")
    elif damage == "escaping path":
        location["paths"]["chromium"] = "../outside/chrome.exe"
        target.write_text(json.dumps(record), encoding="utf-8")
    elif damage == "unknown field":
        record["installed_by"] = "someone"
        target.write_text(json.dumps(record), encoding="utf-8")
    else:
        target.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    item = ComponentItem.LOCAL_AI if damage == "foreign item" else ComponentItem.BROWSER

    assert read_component_record(item, records_root=records_root).state is ComponentRecordState.UNREADABLE
    assert locate_component(item, records_root=records_root).outcome is ComponentLocateOutcome.RECORD_UNREADABLE
