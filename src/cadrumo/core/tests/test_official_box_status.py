"""Canonical ownership of the official-box classification vocabulary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ... import core
from .. import OfficialBoxStatus
from .. import _official_box_status as owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_official_box_status_is_the_single_public_core_identity() -> None:
    assert core.OfficialBoxStatus is owner.OfficialBoxStatus
    assert tuple(OfficialBoxStatus) == (
        OfficialBoxStatus.ADDRESSED,
        OfficialBoxStatus.REPRESENTED_VIA_BINDING,
        OfficialBoxStatus.UNDEFINED,
    )
    assert tuple(OfficialBoxStatus.__members__) == (
        "ADDRESSED",
        "REPRESENTED_VIA_BINDING",
        "UNDEFINED",
    )
    assert tuple(member.value for member in OfficialBoxStatus) == (
        "addressed",
        "represented_via_binding",
        "undefined",
    )

    source_root = Path(__file__).parents[2]
    declarations = [
        path.resolve()
        for path in source_root.rglob("*.py")
        if any(
            isinstance(node, ast.ClassDef) and node.name == "OfficialBoxStatus"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]
    assert declarations == [Path(owner.__file__).resolve()]
