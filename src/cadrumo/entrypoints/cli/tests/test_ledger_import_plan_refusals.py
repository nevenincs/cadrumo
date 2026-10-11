"""The import command hands the operation what the operator named and reads the plan's refusals back.

The operation plans a directory into its files. The command submits the path
as typed, one entry, and an import that read nothing because of the plan is
refused to the operator in the words it always was: an empty directory names
the directory the operator typed, and an over-long plan states the file limit.

The runtime submission is stood in for here: what is under test is what the
command sends and how it words what comes back. The operation's own planning
runs through the real executor beside the other entrypoint tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.actions_import import LedgerProviderID
from ....application.ledger.import_operation import (
    MAX_LEDGER_IMPORT_FILES,
    LedgerImportFileRefusal,
    LedgerImportResultProjection,
)
from ....core.i18n.render import tr
from ....core.operations import OperationEffect
from .. import _ledger_import_cli
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _submission_refused_with(
    monkeypatch: pytest.MonkeyPatch, reason_code: Literal["empty_directory", "file_limit"], *, named: Path
) -> list[tuple[Path, ...]]:
    """Stand in for the runtime submission with a result whose plan read nothing, and record what was sent."""
    submitted: list[tuple[Path, ...]] = []

    def submit(_ctx: typer.Context, *, files: tuple[Path, ...], **_options: object) -> object:
        submitted.append(files)
        return RegisteredOperationCompletion(
            operation_id="a" * 64,
            projection=LedgerImportResultProjection(
                profile_id=_PROFILE,
                rows=0,
                imported=0,
                skipped=0,
                likely_duplicates=0,
                dry_run=False,
                verify=False,
                bucket_id=str(_PROFILE),
                refused_files=(LedgerImportFileRefusal(file_name=named.name, reason_code=reason_code),),
            ),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(_ledger_import_cli, "import_ledger_sources_for_cli", submit)
    return submitted


def _import(named: Path) -> None:
    _ledger_import_cli.ledger_import(cast(typer.Context, object()), named, LedgerProviderID.AUTO)


def test_a_directory_is_submitted_as_typed_and_an_empty_one_is_refused_by_its_typed_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "a.csv").write_text("x", encoding="utf-8")
    (folder / "b.csv").write_text("x", encoding="utf-8")
    submitted = _submission_refused_with(monkeypatch, "empty_directory", named=folder)

    with pytest.raises(typer.BadParameter) as refused:
        _import(folder)

    # One entry, the directory itself: the command expands nothing.
    assert submitted == [(folder,)]
    assert refused.value.message == tr("cli.ledger.import.empty_directory", path=str(folder))


def test_an_over_long_plan_is_refused_with_the_file_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "statements"
    folder.mkdir()
    submitted = _submission_refused_with(monkeypatch, "file_limit", named=folder)

    with pytest.raises(typer.BadParameter) as refused:
        _import(folder)

    assert submitted == [(folder,)]
    assert refused.value.message == tr(
        "cli.ledger.errors.command_input_invalid",
        details=f"ledger import accepts at most {MAX_LEDGER_IMPORT_FILES} files per operation",
    )
