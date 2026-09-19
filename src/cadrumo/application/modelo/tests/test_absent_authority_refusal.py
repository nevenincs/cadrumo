"""Modelo registry guards when no published authority resolves at all."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.period import Period
from ....domain.calculations.registry import authority as authority_module
from ....domain.calculations.registry.errors import AuthorityDescriptorUnavailableError
from .._registry_helpers import absent_authority_file, reject_unknown_override_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def unpublished_authority_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point resolution at an authority directory nobody has published into.

    This is the state a fresh clone is in before the authority is generated,
    so the guards below answer the question an operator actually arrives with.
    The process-shared authority owner is reset for the test because a cached
    one would answer from the generation this checkout already holds.
    """
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)
    return tmp_path


def test_override_guard_reports_the_absent_authority_rather_than_a_missing_root(
    unpublished_authority_root: Path,
) -> None:
    with (
        override_settings(cadrumo_authority_root=unpublished_authority_root),
        pytest.raises(AuthorityDescriptorUnavailableError) as refusal,
    ):
        reject_unknown_override_casillas(
            modelo="303",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "1T"),
            overrides={"01": Decimal("1")},
        )
    error = refusal.value
    assert error.authority_root_configured is True
    assert error.searched_path.parent.resolve() == unpublished_authority_root.resolve()
    assert error.context is not None
    assert error.context["publish_command"] == "python -m dev.registry.pipeline publish-authority"


def test_absent_authority_file_names_the_file_the_read_could_not_open() -> None:
    missing = Path("authority-0000.sqlite3")
    assert absent_authority_file(FileNotFoundError(2, "No such file", str(missing))) == str(missing)


def test_absent_authority_file_falls_back_to_the_error_text_without_a_filename() -> None:
    assert absent_authority_file(FileNotFoundError("the generation is gone")) == "the generation is gone"
