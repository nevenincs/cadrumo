"""A journal root is prepared once per directory, and every replacement is noticed.

Each journal write used to create the storage root and the journal root and
reapply the journal root's mode, so a profile save paid that work for every
transition. The work now runs once for the directory a repository prepared;
a removed, replaced, relinked or re-moded root is prepared or refused exactly
as before. The counts come from the interpreter's audit events, so they are
the filesystem calls the repository really makes.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from ..config_reset_repository import (
    ConfigResetJournalCorruptError,
    ConfigResetJournalError,
    ConfigResetJournalNotFoundError,
)
from ..journal_repository import JournalRepositoryBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIRNAME = "preparation-journals"


class _Operation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    started_at: datetime


def _repository(storage_root: Path) -> JournalRepositoryBase[_Operation]:
    return JournalRepositoryBase[_Operation](
        journal_dirname=_DIRNAME,
        storage_root=storage_root,
        parse_operation=_Operation.model_validate_json,
        error_type=ConfigResetJournalError,
        not_found_type=ConfigResetJournalNotFoundError,
        corrupt_type=ConfigResetJournalCorruptError,
        subject="preparation journal",
        id_subject="preparation journal",
    )


def _operation(index: int) -> _Operation:
    return _Operation(operation_id=f"{index:064x}", started_at=datetime(2026, 10, 22, tzinfo=UTC))


_RECORDING: list[Counter[tuple[str, str]] | None] = [None]


def _record_directory_calls(event: str, arguments: tuple[object, ...]) -> None:
    counter = _RECORDING[0]
    if counter is None or event not in {"os.mkdir", "os.chmod"} or not arguments:
        return
    target = arguments[0]
    if isinstance(target, (str, os.PathLike)):
        counter[(event, os.path.normcase(os.fspath(target)))] += 1


# An audit hook cannot be removed; outside a recording it returns at once.
sys.addaudithook(_record_directory_calls)


@contextmanager
def _directory_calls() -> Generator[Counter[tuple[str, str]]]:
    counter: Counter[tuple[str, str]] = Counter()
    _RECORDING[0] = counter
    try:
        yield counter
    finally:
        _RECORDING[0] = None


def _key(event: str, path: Path) -> tuple[str, str]:
    return (event, os.path.normcase(os.fspath(path)))


def _bind_directory(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    os.symlink(target, link, target_is_directory=True)


def test_many_writes_create_and_restrict_the_root_once(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "state")
    with _directory_calls() as calls:
        for index in range(12):
            repository.save(_operation(index))

    assert calls[_key("os.chmod", repository.root)] == 1
    assert calls[_key("os.mkdir", tmp_path / "state")] == 1
    assert len(repository.list()) == 12


def _counting_resolves(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    resolved: list[Path] = []
    original = Path.resolve

    def counted(self: Path, strict: bool = False) -> Path:
        resolved.append(self)
        return original(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", counted)
    return resolved


def test_repeated_reads_resolve_the_validated_root_no_further(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    resolved = _counting_resolves(monkeypatch)

    for _ in range(5):
        repository.load(_operation(1).operation_id)

    assert repository.root not in resolved


def test_a_root_replaced_after_validation_is_resolved_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    shutil.rmtree(repository.root)
    repository.root.mkdir()
    resolved = _counting_resolves(monkeypatch)

    assert repository.list() == ()

    assert repository.root in resolved


def test_a_root_removed_between_writes_is_created_and_restricted_again(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    shutil.rmtree(repository.root)

    with _directory_calls() as calls:
        repository.save(_operation(2))

    assert calls[_key("os.chmod", repository.root)] == 1
    assert [operation.operation_id for operation in repository.list()] == [_operation(2).operation_id]


def test_a_root_replaced_by_another_directory_is_prepared_again(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    repository.root.rename(tmp_path / "moved-away")
    repository.root.mkdir()

    with _directory_calls() as calls:
        repository.save(_operation(2))

    assert calls[_key("os.chmod", repository.root)] == 1


def test_a_link_swapped_in_after_preparation_is_refused_without_writing_through_it(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    redirected = tmp_path / "redirected"
    repository.root.rename(redirected)
    _bind_directory(repository.root, redirected)

    with pytest.raises(ConfigResetJournalError, match="symlink or junction"):
        repository.save(_operation(2))
    assert not (redirected / f"{_operation(2).operation_id}.json").exists()


def test_a_file_swapped_in_after_preparation_fails_as_an_unprepared_root_does(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    shutil.rmtree(repository.root)
    repository.root.write_bytes(b"")

    with pytest.raises(FileExistsError):
        repository.save(_operation(2))
    with pytest.raises(FileExistsError):
        _repository(tmp_path).save(_operation(2))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX directory modes are asserted only on POSIX")
def test_a_root_whose_mode_changed_is_restricted_again(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save(_operation(1))
    repository.root.chmod(0o755)

    repository.save(_operation(2))

    assert stat.S_IMODE(repository.root.stat().st_mode) == 0o700
