"""The backend's number reader against the table the desktop reader is held to."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....core.external_constants import OutputLanguage
from ..edit_number_parsing import read_edit_number_lexeme
from ..edit_parse_errors import ModeloEditParseRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TABLE = Path(__file__).parents[5] / "native/desktop/frontend/tests/shared/locale-decimal-readings.json"


def _reading(lexeme: str, language: OutputLanguage) -> str | None:
    try:
        return format(read_edit_number_lexeme(lexeme, language, []), "f")
    except ModeloEditParseRefusedError:
        return None


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_reader_gives_every_outcome_in_the_shared_table(language: OutputLanguage) -> None:
    rows = json.loads(_TABLE.read_text(encoding="utf-8"))
    assert rows
    for row in rows:
        assert _reading(row["lexeme"], language) == row[language.value], row["lexeme"]
