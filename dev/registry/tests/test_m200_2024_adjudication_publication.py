"""Safety tests specific to the M200 S14/S15 publisher's target path."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_adjudication_publication as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_target_path_refuses_an_intermediate_link_before_any_transaction(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "modelos"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - Windows host policy can deny link creation.
        pytest.skip(f"host does not permit link detector fixture: {exc}")

    with pytest.raises(RegistryValidationError, match="casilla path is unsafe"):
        subject._casillas_root(root)


def test_target_receipt_fingerprints_nested_non_toml_members(tmp_path: Path) -> None:
    root = tmp_path / "casillas"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "c00001.toml").write_text("first\n", encoding="utf-8")
    (nested / "unexpected.bin").write_bytes(b"must-be-bound\n")

    fingerprint = dict(subject._tree_fingerprint(root))

    assert set(fingerprint) == {"c00001.toml", "nested/unexpected.bin"}
