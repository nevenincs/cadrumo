"""Cached API stubs are admitted only in their declared shape and key."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..manager import _published_stubs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize("stubs", [{"module.rst": 1}, {"module.rst": None}, {}])
def test_published_api_stubs_reject_malformed_content(tmp_path: Path, stubs: dict[str, object]) -> None:
    (tmp_path / "stubs.json").write_text(json.dumps({"key": "current", "stubs": stubs}), encoding="utf-8")
    assert _published_stubs(tmp_path, "current") is None


def test_published_api_stubs_require_the_expected_key(tmp_path: Path) -> None:
    (tmp_path / "stubs.json").write_text(
        json.dumps({"key": "current", "stubs": {"module.rst": "content"}}), encoding="utf-8"
    )
    assert _published_stubs(tmp_path, "other") is None
    assert _published_stubs(tmp_path, "current") == {"module.rst": "content"}
