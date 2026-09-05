"""Direct behavioral proof for the application-owned import preparation boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..import_preparation import LedgerImportPathRefusedError, prepare_ledger_import_command
from ..models import LedgerSourceImportCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_prepare_strips_the_entry_and_constructs_the_auto_provider_command(tmp_path: Path) -> None:
    source = tmp_path / "statement.csv"
    source.write_text("date,amount\n2026-01-01,10.00\n", encoding="utf-8")

    command = prepare_ledger_import_command(f"  {source}  ", bucket_id="bucket-1")

    assert isinstance(command, LedgerSourceImportCommand)
    assert command.bucket_id == "bucket-1"
    assert command.path == source
    assert command.provider == "auto"
    assert command.period is None


def test_prepare_expands_an_existing_home_path_before_refusing_a_directory() -> None:
    """``~`` must be expanded; otherwise this branch would be an absent-path refusal."""
    assert Path("~").expanduser().is_dir()

    with pytest.raises(LedgerImportPathRefusedError, match="the entered source is not a file"):
        prepare_ledger_import_command("~", bucket_id="bucket-1")


@pytest.mark.parametrize(
    ("raw_path", "reason"),
    [
        ("", "no source path was entered"),
        ("  \t", "no source path was entered"),
    ],
)
def test_prepare_refuses_blank_entries(raw_path: str, reason: str) -> None:
    with pytest.raises(LedgerImportPathRefusedError, match=reason):
        prepare_ledger_import_command(raw_path, bucket_id="bucket-1")


def test_prepare_refuses_an_absent_path(tmp_path: Path) -> None:
    with pytest.raises(LedgerImportPathRefusedError, match="the entered source does not exist"):
        prepare_ledger_import_command(str(tmp_path / "absent.csv"), bucket_id="bucket-1")


def test_prepare_refuses_a_directory(tmp_path: Path) -> None:
    with pytest.raises(LedgerImportPathRefusedError, match="the entered source is not a file"):
        prepare_ledger_import_command(str(tmp_path), bucket_id="bucket-1")


def test_prepare_refuses_an_unreadable_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "statement.csv"
    source.write_text("date,amount\n", encoding="utf-8")

    def refuse_read(_self: Path, *_args: object, **_kwargs: object) -> object:
        raise OSError("read denied")

    monkeypatch.setattr(Path, "open", refuse_read)

    with pytest.raises(LedgerImportPathRefusedError, match="the entered source cannot be read"):
        prepare_ledger_import_command(str(source), bucket_id="bucket-1")
