"""One unreadable statement must not discard a folder's other imports.

The folder import ran its per-file work in a bare comprehension with no per-item
guard, so the first file that raised ended the run and threw away every result
already produced. An operator importing a quarter of statements lost the whole
run to one bad file, and the totals never mentioned it.

These tests pin both halves: a bad file is reported and costs only itself, and a
folder of good files still imports every one — because "never abort" is also
satisfied by a runner that refuses everything, and that would be worse.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Give every case an active profile.

    Without it the command refuses on "no active profile" and exits before the
    folder loop runs at all -- so each test decides its outcome before the code
    under test executes, which is how all four passed and said nothing.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
        )
        yield

_GOOD_STATEMENT = (
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda\n"
    "08/04/2026;08/04/2026;Transferencia recibida CLIENTE UNO;1500,25;4300,75;EUR\n"
    "09/04/2026;09/04/2026;Pago alquiler oficina;-800,00;3500,75;EUR\n"
)
#: A CSV the provider cannot read as any bank layout: real columns, no statement.
_POISONED_STATEMENT = "colonna_a,colonna_b\nvalore,altro\n"


def _folder(tmp_path: Path, files: dict[str, str]) -> Path:
    folder = tmp_path / "statements"
    folder.mkdir()
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8")
    return folder


def test_one_poisoned_file_does_not_discard_the_rest_of_the_folder(tmp_path: Path) -> None:
    """The defect this closes: a bad file costs itself and nothing else."""
    folder = _folder(
        tmp_path,
        {
            "a_poisoned.csv": _POISONED_STATEMENT,
            "b_good.csv": _GOOD_STATEMENT,
            "c_good.csv": _GOOD_STATEMENT,
        },
    )

    result = invoke_cached_cli(
        ["app", "ledger", "import", "--file", str(folder), "--provider", "auto", "--dry-run"],
    )

    # The poisoned file sorts FIRST, so under the old comprehension it aborted
    # the run before either good file was reached.
    assert "a_poisoned.csv" in result.output, result.output
    assert "rows" in result.output.lower()


def test_a_folder_of_good_files_still_imports_every_one(tmp_path: Path) -> None:
    """Positive control: 'never abort' must not be satisfied by refusing everything.

    Without this, a guard that swallowed every file into a refusal list would
    satisfy the test above perfectly while importing nothing at all.
    """
    folder = _folder(tmp_path, {"a_good.csv": _GOOD_STATEMENT, "b_good.csv": _GOOD_STATEMENT})

    result = invoke_cached_cli(
        ["app", "ledger", "import", "--file", str(folder), "--provider", "auto", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "a_good.csv" not in result.output, "no file should be reported refused"
    # Two files of two rows each. Pinned exactly: an ``or "4"`` fallback would
    # match almost any output and assert nothing about the aggregate, which is
    # the half of this fix that must not silently describe a subset.
    assert re.search(r"\b4\b", result.output), result.output


def test_a_single_unreadable_file_is_still_a_hard_refusal(tmp_path: Path) -> None:
    """Guarding the folder must not downgrade the single-file error to a warning.

    ``_resolve_import_paths`` returns a one-element list for a plain file, so a
    naive per-item guard would catch that failure too and report an import that
    imported nothing as a success.
    """
    lone = tmp_path / "poisoned.csv"
    lone.write_text(_POISONED_STATEMENT, encoding="utf-8")

    result = invoke_cached_cli(
        ["app", "ledger", "import", "--file", str(lone), "--provider", "auto", "--dry-run"],
    )

    assert result.exit_code != 0, result.output
    # Discriminated by the OFFENDING FILE's name, not by the refusal prose:
    # an unrelated internal error satisfies "failed" just as well, and did once
    # while this was being written. The name is data rather than localised
    # text, so this does not break under a different catalogue either.
    assert "poisoned.csv" in result.output, result.output


def test_a_folder_where_every_file_fails_is_a_hard_refusal(tmp_path: Path) -> None:
    """Importing nothing is a failure however many files were offered."""
    folder = _folder(tmp_path, {"a.csv": _POISONED_STATEMENT, "b.csv": _POISONED_STATEMENT})

    result = invoke_cached_cli(
        ["app", "ledger", "import", "--file", str(folder), "--provider", "auto", "--dry-run"],
    )

    assert result.exit_code != 0, result.output
    assert "a.csv" in result.output, result.output
