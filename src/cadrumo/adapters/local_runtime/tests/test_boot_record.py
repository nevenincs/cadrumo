"""Real-filesystem publication, strict reading and exact removal of the runtime boot record."""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import StorageMode
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path

from ..boot_record import (
    MAXIMUM_BOOT_RECORD_BYTES,
    RuntimeBootRecord,
    RuntimeBootRecordPublication,
    RuntimeBootRecordUnavailable,
    current_runtime_boot_record,
    read_runtime_boot_record,
    runtime_boot_record_path,
    runtime_package_directory,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_VALID = (
    b'{"admission":"native","boot_id":"00000000-0000-4000-8000-000000000001","package_directory":null,'
    b'"pid":4242,"process_created":133000000000000000,"schema_version":1,"version":"1.2.3"}'
)


def _record(*, package_directory: str | None = None) -> RuntimeBootRecord:
    return RuntimeBootRecord(
        boot_id=uuid4(),
        pid=4242,
        process_created=133_000_000_000_000_000,
        version="1.2.3",
        package_directory=package_directory,
        admission="native",
    )


def _write_raw(root: Path, payload: bytes) -> Path:
    path = runtime_boot_record_path(root)
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(payload)
    return path


def test_the_record_lives_beside_the_installation_identity(tmp_path: Path) -> None:
    assert runtime_boot_record_path(tmp_path) == storage_path(
        StorageCategory.RUNTIME_BOOT_RECORD,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    with pytest.raises(RuntimeRefusalError) as refused:
        runtime_boot_record_path(Path("relative-root"))
    assert refused.value.reason is RuntimeRefusalCode.ROOT_MISMATCH


def test_a_published_record_reads_back_exactly(tmp_path: Path) -> None:
    package = tmp_path / "package" / "1.2.3"
    record = _record(package_directory=str(package))
    publication = RuntimeBootRecordPublication(storage_root=tmp_path, record=record)
    assert publication.publish()
    assert read_runtime_boot_record(storage_root=tmp_path) == record
    stored = runtime_boot_record_path(tmp_path).read_bytes()
    # Canonical JSON: sorted members, compact separators, exactly the declared fields.
    assert stored.startswith(b'{"admission":"native","boot_id":')
    assert set(RuntimeBootRecord.model_fields) == {
        "schema_version",
        "boot_id",
        "pid",
        "process_created",
        "version",
        "package_directory",
        "admission",
    }


def test_the_independent_fixture_bytes_parse_to_the_declared_record(tmp_path: Path) -> None:
    _write_raw(tmp_path, _VALID)
    parsed = read_runtime_boot_record(storage_root=tmp_path)
    assert isinstance(parsed, RuntimeBootRecord)
    assert str(parsed.boot_id) == "00000000-0000-4000-8000-000000000001"
    assert (parsed.pid, parsed.process_created, parsed.version) == (4242, 133_000_000_000_000_000, "1.2.3")
    assert parsed.package_directory is None and parsed.admission == "native"


def test_a_missing_directory_or_record_is_absent_and_nothing_is_created(tmp_path: Path) -> None:
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    assert tuple(tmp_path.iterdir()) == ()
    (tmp_path / ".runtime").mkdir()
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    assert tuple((tmp_path / ".runtime").iterdir()) == ()


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        _VALID.replace(b'"pid":4242,', b'"pid":4242,"pid":4243,'),
        _VALID.replace(b'"pid":4242,', b'"pid":4242,"user":"someone",'),
        _VALID.replace(b'"schema_version":1', b'"schema_version":2'),
        _VALID.replace(b'"pid":4242', b'"pid":"4242"'),
        _VALID.replace(b'"pid":4242', b'"pid":0'),
        _VALID.replace(b'"admission":"native"', b'"admission":"relaxed"'),
        _VALID.replace(b'"package_directory":null', b'"package_directory":"relative/package"'),
        _VALID.replace(b'"process_created":133000000000000000', b'"process_created":NaN'),
        _VALID.replace(b',"version":"1.2.3"', b""),
        # Valid JSON whose only defect is its size.
        _VALID + b" " * MAXIMUM_BOOT_RECORD_BYTES,
    ],
    ids=(
        "invalid-json",
        "duplicate-member",
        "unknown-member",
        "unknown-schema",
        "string-pid",
        "zero-pid",
        "unknown-admission",
        "relative-package",
        "non-finite-constant",
        "missing-member",
        "oversized",
    ),
)
def test_anything_but_one_strict_record_is_unreadable(tmp_path: Path, payload: bytes) -> None:
    path = _write_raw(tmp_path, payload)
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.UNREADABLE
    assert path.read_bytes() == payload


def test_a_directory_in_place_of_the_record_is_unreadable(tmp_path: Path) -> None:
    runtime_boot_record_path(tmp_path).mkdir(parents=True)
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.UNREADABLE


def test_a_reboot_replaces_the_record_and_the_earlier_boot_cannot_remove_it(tmp_path: Path) -> None:
    earlier_record, later_record = _record(), _record()
    earlier = RuntimeBootRecordPublication(storage_root=tmp_path, record=earlier_record)
    assert earlier.publish()
    later = RuntimeBootRecordPublication(storage_root=tmp_path, record=later_record)
    assert later.publish()
    assert read_runtime_boot_record(storage_root=tmp_path) == later_record
    earlier.withdraw()
    assert read_runtime_boot_record(storage_root=tmp_path) == later_record


def test_a_corrupt_record_left_behind_is_replaced(tmp_path: Path) -> None:
    _write_raw(tmp_path, b'{"pid":1,"pid":2}')
    record = _record()
    assert RuntimeBootRecordPublication(storage_root=tmp_path, record=record).publish()
    assert read_runtime_boot_record(storage_root=tmp_path) == record


def test_withdrawal_removes_only_this_boot_and_ends_publication(tmp_path: Path) -> None:
    publication = RuntimeBootRecordPublication(storage_root=tmp_path, record=_record())
    assert publication.publish()
    publication.withdraw()
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    assert (tmp_path / ".runtime").is_dir()
    assert not publication.publish()
    assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
    # Withdrawal is idempotent once nothing is published.
    publication.withdraw()


def test_withdrawal_before_publication_writes_nothing(tmp_path: Path) -> None:
    publication = RuntimeBootRecordPublication(storage_root=tmp_path, record=_record())
    publication.withdraw()
    assert not publication.publish()
    assert tuple(tmp_path.iterdir()) == ()


def test_a_missing_storage_root_refuses_publication(tmp_path: Path) -> None:
    publication = RuntimeBootRecordPublication(storage_root=tmp_path / "missing", record=_record())
    with pytest.raises(RuntimeRefusalError) as refused:
        publication.publish()
    assert refused.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert tuple(tmp_path.iterdir()) == ()


def test_only_a_native_package_root_names_a_package_directory(tmp_path: Path) -> None:
    root = tmp_path / "Cadrumo" / "1.2.3"
    (root / "data").mkdir(parents=True)
    interpreter = root / ("python.exe" if sys.platform == "win32" else "python")
    assert runtime_package_directory(interpreter, mode=StorageMode.INSTALLED) is None
    (root / "data" / "package-manifest.json").write_bytes(b"{}")
    assert runtime_package_directory(interpreter, mode=StorageMode.INSTALLED) == str(root)
    assert runtime_package_directory(interpreter, mode=StorageMode.DEVELOPMENT) is None
    assert runtime_package_directory(Path("python"), mode=StorageMode.INSTALLED) is None


def test_this_process_describes_itself_with_its_native_creation_stamp() -> None:
    boot_id = uuid4()
    first = current_runtime_boot_record(boot_id=boot_id, version="1.2.3", admission="development")
    second = current_runtime_boot_record(boot_id=boot_id, version="1.2.3", admission="development")
    assert first == second
    assert first.pid == os.getpid() and first.process_created > 0
    # The test runner imports the checkout, which has no versioned package.
    assert first.package_directory is None
    if sys.platform == "win32":
        import win32api
        import win32process

        # pywin32 reports the same kernel creation time, truncated to milliseconds.
        created = win32process.GetProcessTimes(win32api.GetCurrentProcess())["CreationTime"]
        assert isinstance(created, datetime.datetime)
        elapsed = created - datetime.datetime(1601, 1, 1, tzinfo=datetime.UTC)
        ticks = (elapsed.days * 86_400 + elapsed.seconds) * 10_000_000 + elapsed.microseconds * 10
        assert first.process_created // 10_000 == ticks // 10_000
