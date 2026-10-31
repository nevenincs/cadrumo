"""Fixture namespace roots follow pytest's controlled temporary directory."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.tests import process_support

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_posix_namespace_base_uses_pinned_temp_without_an_extra_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(process_support, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert process_support.runtime_namespace_base.__wrapped__() == tmp_path.resolve()
    assert list(tmp_path.iterdir()) == []
