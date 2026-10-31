"""The manager strings input is a typed language-to-string projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..generate import _manager_strings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_manager_strings_accept_a_language_mapping(tmp_path: Path) -> None:
    source = tmp_path / "strings.json"
    source.write_text(json.dumps({"en": {"save": "Save"}}), encoding="utf-8")
    assert _manager_strings(source) == {"en": {"save": "Save"}}


@pytest.mark.parametrize("document", [[], {"en": []}, {"en": {"save": 1}}, {"en": {"save": None}}])
def test_manager_strings_refuse_malformed_input(tmp_path: Path, document: object) -> None:
    source = tmp_path / "strings.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="manager strings"):
        _manager_strings(source)
