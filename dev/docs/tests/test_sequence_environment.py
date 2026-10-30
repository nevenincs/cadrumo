"""Sequence children discard operator routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.sequences.checks import english_pinned_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_child_does_not_inherit_operator_storage_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "parent-state"))
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "hu")
    environment = english_pinned_environment()
    assert "CADRUMO_STORAGE_ROOT" not in environment
    assert "AEAT_OUTPUT_LANGUAGE" not in environment
    assert environment["CADRUMO_OUTPUT_LANGUAGE"] == "en"
