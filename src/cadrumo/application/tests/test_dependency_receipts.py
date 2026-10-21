"""Setup receipts on a real filesystem: atomic round trips, unreadable files and manifest checks."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...core.config import Settings
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ..dependency_receipts import (
    DependencyReceipt,
    DependencyReceiptFile,
    DependencyReceiptState,
    DependencyReceiptStore,
    build_file_manifest,
    check_file_manifest,
    dependency_receipts_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VERIFIED = datetime(2026, 10, 18, 10, 0, tzinfo=UTC)


def _install(root: Path) -> None:
    (root / "chrome-win").mkdir(parents=True)
    (root / "chrome-win" / "chrome.exe").write_bytes(b"\x4d\x5a executable")
    (root / "chrome-win" / "resources.pak").write_bytes(b"resources" * 100)
    (root / "INSTALLATION_COMPLETE").write_bytes(b"")


def test_receipts_live_installation_wide_beside_the_components(tmp_path: Path) -> None:
    location = storage_location(StorageCategory.DEPENDENCY_RECEIPTS)
    assert location.subpath == "components/receipts"
    settings = Settings(cadrumo_local_storage_root=tmp_path)
    assert dependency_receipts_root(settings).relative_to(tmp_path.resolve()).as_posix() == location.subpath


def test_manifest_records_every_file_once_with_its_digest(tmp_path: Path) -> None:
    root = tmp_path / "chromium-1187"
    _install(root)
    manifest = build_file_manifest(root)
    assert [entry.path for entry in manifest] == [
        "INSTALLATION_COMPLETE",
        "chrome-win/chrome.exe",
        "chrome-win/resources.pak",
    ]
    executable = manifest[1]
    assert executable.sha256 == hashlib.sha256(b"\x4d\x5a executable").hexdigest()
    assert executable.size_bytes == len(b"\x4d\x5a executable")
    assert build_file_manifest(root, files=(Path("chrome-win/chrome.exe"),)) == (executable,)


def test_store_round_trips_and_distinguishes_absent_from_unreadable(tmp_path: Path) -> None:
    root = tmp_path / "chromium-1187"
    _install(root)
    store = DependencyReceiptStore(tmp_path / "receipts")
    assert store.read("browser").state is DependencyReceiptState.ABSENT

    receipt = DependencyReceipt(
        item_id="browser",
        version="1187",
        files=build_file_manifest(root),
        verified_at=_VERIFIED,
        hosts=("cdn.playwright.dev",),
    )
    store.write(receipt)
    reading = store.read("browser")
    assert reading.state is DependencyReceiptState.PRESENT
    assert reading.receipt == receipt
    assert sorted(path.name for path in store.root.iterdir()) == ["browser.json"]

    (store.root / "local_ai.json").write_text("{not json", encoding="utf-8")
    assert store.read("local_ai").state is DependencyReceiptState.UNREADABLE
    (store.root / "local_ai.json").write_bytes((store.root / "browser.json").read_bytes())
    assert store.read("local_ai").state is DependencyReceiptState.UNREADABLE

    store.remove("browser")
    store.remove("browser")
    assert store.read("browser").state is DependencyReceiptState.ABSENT
    with pytest.raises(ValueError):
        store.read("chromium")


def test_manifest_check_finds_changed_and_missing_files(tmp_path: Path) -> None:
    root = tmp_path / "chromium-1187"
    _install(root)
    receipt = DependencyReceipt(
        item_id="browser", version="1187", files=build_file_manifest(root), verified_at=_VERIFIED
    )

    assert check_file_manifest(root, receipt).intact is True
    quick = check_file_manifest(root, receipt, only=("chrome-win/chrome.exe",))
    assert (quick.intact, quick.checked) == (True, 1)

    (root / "chrome-win" / "chrome.exe").write_bytes(b"\x4d\x5a executablE")
    (root / "chrome-win" / "resources.pak").unlink()
    full = check_file_manifest(root, receipt)
    assert full.changed == ("chrome-win/chrome.exe",)
    assert full.missing == ("chrome-win/resources.pak",)
    assert full.intact is False
    assert check_file_manifest(root, receipt, only=("chrome-win/unrecorded.dll",)).missing == (
        "chrome-win/unrecorded.dll",
    )


def test_receipt_fields_refuse_escaping_paths_naive_times_and_unordered_files() -> None:
    digest = "0" * 64
    for path in ("../outside", "/abs/file", "C:/x", "a\\b", "a//b", "./a"):
        with pytest.raises(ValidationError):
            DependencyReceiptFile(path=path, size_bytes=1, sha256=digest)
    files = (
        DependencyReceiptFile(path="b", size_bytes=1, sha256=digest),
        DependencyReceiptFile(path="a", size_bytes=1, sha256=digest),
    )
    with pytest.raises(ValidationError, match="path order"):
        DependencyReceipt(item_id="browser", version=None, files=files, verified_at=_VERIFIED)
    with pytest.raises(ValidationError):
        DependencyReceipt(item_id="browser", version=None, files=(), verified_at=_VERIFIED.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        DependencyReceipt(
            item_id="browser", version=None, files=(), verified_at=_VERIFIED.astimezone(timezone(timedelta(hours=2)))
        )
