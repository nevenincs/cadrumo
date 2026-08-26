"""Canonical ownership of the official-casilla classification vocabulary."""

from __future__ import annotations

from pathlib import Path

import pytest

from ... import core
from ...tests import modules_declaring_class
from .. import EstadoCasillaOficial
from .. import _estado_casilla_oficial as owner
from ..directory_scan import DirectoryEntryKind, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TEXT_BEARING_SUFFIXES = frozenset(
    {
        ".bat",
        ".cfg",
        ".cmd",
        ".conf",
        ".css",
        ".csv",
        ".gql",
        ".graphql",
        ".htm",
        ".html",
        ".ini",
        ".j2",
        ".jinja",
        ".jinja2",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".md",
        ".ps1",
        ".py",
        ".pyi",
        ".rst",
        ".scss",
        ".seq",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsv",
        ".tsx",
        ".txt",
        ".xml",
        ".xsd",
        ".yaml",
        ".yml",
    },
)


def _retired_family() -> frozenset[str]:
    return frozenset(
        {
            "Official" + "BoxStatus",
            "official_box_" + "status",
            "official_box_" + "classification",
            "classify_official_" + "boxes",
            "_official_box_" + "status.py",
            "_official_box_representation_" + "channels",
            "official_" + "status",
            "modelo-review-filter-official-" + "status",
            "flows.modelo_review.filter.official_" + "status",
            "option.official_" + "status",
        },
    )


def _retired_family_occurrences(*roots: Path) -> set[tuple[str, str]]:
    repository_root = Path(__file__).parents[4]
    candidates = {
        path
        for root in roots
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix.lower() in _TEXT_BEARING_SUFFIXES
    }
    retired = _retired_family()
    occurrences: set[tuple[str, str]] = set()
    for path in candidates:
        reported_path = (
            path.relative_to(repository_root).as_posix() if path.is_relative_to(repository_root) else path.as_posix()
        )
        content = path.read_text(encoding="utf-8", errors="surrogateescape")
        occurrences.update((reported_path, token) for token in retired if token in reported_path or token in content)
    return occurrences


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

    declarations = list(modules_declaring_class("EstadoCasillaOficial"))
    assert declarations == [Path(owner.__file__).resolve()]


def test_retired_english_family_is_absent_from_code_and_locale_surfaces() -> None:
    repository_root = Path(__file__).parents[4]
    assert _retired_family_occurrences(repository_root / "src", repository_root / "scaffold") == set()


def test_retired_family_scan_bites_on_a_non_python_dev_surface(tmp_path: Path) -> None:
    planted = tmp_path / "scaffold" / "locales" / "planted.yml"
    planted.parent.mkdir(parents=True)
    retired_token = "official_" + "status"
    planted.write_text(f"filter:\n  {retired_token}: retired\n", encoding="utf-8")

    assert _retired_family_occurrences(tmp_path / "scaffold") == {
        (planted.as_posix(), retired_token),
    }
