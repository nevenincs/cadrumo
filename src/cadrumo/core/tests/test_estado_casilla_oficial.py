"""Canonical ownership of the official-casilla classification vocabulary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ... import core
from .. import EstadoCasillaOficial
from .. import _estado_casilla_oficial as owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_estado_casilla_oficial_is_the_single_public_core_identity() -> None:
    assert core.EstadoCasillaOficial is owner.EstadoCasillaOficial
    assert tuple(EstadoCasillaOficial) == (
        EstadoCasillaOficial.ADDRESSED,
        EstadoCasillaOficial.REPRESENTED_VIA_BINDING,
        EstadoCasillaOficial.UNDEFINED,
    )
    assert tuple(EstadoCasillaOficial.__members__) == (
        "ADDRESSED",
        "REPRESENTED_VIA_BINDING",
        "UNDEFINED",
    )
    assert tuple(member.value for member in EstadoCasillaOficial) == (
        "addressed",
        "represented_via_binding",
        "undefined",
    )

    source_root = Path(__file__).parents[2]
    declarations = [
        path.resolve()
        for path in source_root.rglob("*.py")
        if any(
            isinstance(node, ast.ClassDef) and node.name == "EstadoCasillaOficial"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]
    assert declarations == [Path(owner.__file__).resolve()]


def test_retired_english_family_is_absent_from_code_and_locale_surfaces() -> None:
    retired = {
        "Official" + "BoxStatus",
        "official_box_" + "status",
        "classify_official_" + "boxes",
    }
    repository_root = Path(__file__).parents[4]
    scanned_files = (
        *repository_root.joinpath("src", "cadrumo").rglob("*.py"),
        *repository_root.joinpath("src", "cadrumo", "locales").rglob("*.yml"),
        *repository_root.joinpath("dev", "locales").rglob("*.py"),
    )
    occurrences = {
        (path.relative_to(repository_root).as_posix(), token)
        for path in scanned_files
        for token in retired
        if token in path.read_text(encoding="utf-8")
    }
    retired_paths = {
        path.relative_to(repository_root).as_posix()
        for path in scanned_files
        if any(token in path.name for token in ("official_box_" + "status", "official_box_" + "classification"))
    }
    assert occurrences == set()
    assert retired_paths == set()
