"""An operator-entered path becomes a sealed import, or is refused by name."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..import_preparation import LedgerImportPathRefusedError, prepare_ledger_import
from ..models import LedgerPreparedImportV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "b" * 8


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "statement.csv"
    path.write_text("date,amount\n2026-01-01,10.00\n", encoding="utf-8")
    return path


def test_a_readable_file_becomes_a_sealed_prepared_import(tmp_path: Path) -> None:
    """The import area is entered WITH one of these, and nothing made one before.

    `LedgerPreparedImportV1` was constructed only in tests, so the area was
    permanently refused in a real session while the navigation table listed it.
    """
    prepared = prepare_ledger_import(str(_source(tmp_path)), bucket_id=_BUCKET, choice_id="prepared.1")

    assert isinstance(prepared, LedgerPreparedImportV1)
    assert prepared.choice_id == "prepared.1"
    assert prepared.provider_label_key == "tui.ledger.import.provider.bank"


def test_the_entered_path_never_escapes_the_sealed_command(tmp_path: Path) -> None:
    """A path the operator typed must not reach a frame, a log or a crash report.

    The sealed object is what the screen holds, so its representation is the
    surface that would leak. Asserted on the path AND its parent, because a
    directory is enough to identify a machine and a person.
    """
    source = _source(tmp_path)
    prepared = prepare_ledger_import(str(source), bucket_id=_BUCKET, choice_id="prepared.1")

    rendered = f"{prepared!r} {prepared.choice_id} {prepared.provider_label_key} {prepared.source_label_key}"
    assert str(source) not in rendered
    assert str(source.parent) not in rendered
    assert source.name not in rendered


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        ("", "no source path was entered"),
        ("   ", "no source path was entered"),
        ("<missing>", "the entered source does not exist"),
        ("<directory>", "the entered source is not a file"),
    ],
)
def test_an_unusable_entry_is_refused_at_the_screen_that_caused_it(tmp_path: Path, entry: str, reason: str) -> None:
    """Refused here, not later inside the import service.

    `import_ledger_source` would refuse an unreadable source too, but by then
    the operator has left this screen and the refusal arrives detached from the
    entry that caused it. The message names WHICH condition failed and never
    the path, so a refusal cannot leak what a successful preparation hides.
    """
    resolved = {
        "<missing>": str(tmp_path / "absent.csv"),
        "<directory>": str(tmp_path),
    }.get(entry, entry)

    with pytest.raises(LedgerImportPathRefusedError) as refusal:
        prepare_ledger_import(resolved, bucket_id=_BUCKET, choice_id="prepared.1")

    assert str(refusal.value) == reason
    assert str(tmp_path) not in str(refusal.value)
