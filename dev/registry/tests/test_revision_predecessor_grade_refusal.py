"""Storage inheritance remains independent of revision authority grade."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "999"
_LEGAL_REF = "ley-58-2003:art-29"


def _casilla(revision_id: str, casilla_id: str, *, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n\n'
    )


def _write_edition(
    modelo_dir: Path, revision_id: str, *, year: int, grade: str | None, extra: str, casillas: str
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    grade_line = f'authority_grade = "{grade}"\n' if grade is not None else ""
    (revision_dir / "revision.toml").write_text(
        (
            f'[revisions."{revision_id}"]\n'
            f"{grade_line}"
            f"valid_from = {year}-01-01\n"
            f"valid_to = {year}-12-31\n"
            f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
            f"{extra}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")


def _two_edition_modelo(
    root: Path,
    *,
    predecessor_grade: str | None,
    successor_grade: str | None,
    declare_predecessor: bool,
) -> Path:
    """A three-row 2024 edition and a 2025 edition stating one new row."""
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        grade=predecessor_grade,
        extra="",
        casillas=(
            _casilla("2024", "0001", lineage="base-imponible")
            + _casilla("2024", "0002", lineage="cuota-integra")
            + _casilla("2024", "0003", lineage="cuota-diferencial")
        ),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        grade=successor_grade,
        extra='predecessor = "2024"\n' if declare_predecessor else "",
        casillas=_casilla("2025", "0004", lineage="recargo"),
    )
    return modelo_dir


@pytest.mark.parametrize(
    ("predecessor_grade", "successor_grade"),
    [
        ("filing", "calculation"),
        ("filing", "applicability"),
        ("calculation", "applicability"),
        ("calculation", None),
        ("calculation", "calculation"),
        ("applicability", "filing"),
        (None, None),
        (None, "applicability"),
        ("applicability", None),
    ],
)
def test_a_successor_inherits_without_changing_its_declared_grade(
    tmp_path: Path,
    predecessor_grade: str | None,
    successor_grade: str | None,
) -> None:
    modelo_dir = _two_edition_modelo(
        tmp_path,
        predecessor_grade=predecessor_grade,
        successor_grade=successor_grade,
        declare_predecessor=True,
    )

    modelo = load_modelo_directory(modelo_dir)
    successor = modelo.revisions["2025"]

    assert [casilla.id for casilla in successor.casillas] == ["0001", "0002", "0003", "0004"]
    assert successor.authority_grade is (None if successor_grade is None else RegistryAuthorityGrade(successor_grade))


def test_the_same_lower_graded_successor_loads_as_full_copy_without_the_declaration(tmp_path: Path) -> None:
    modelo_dir = _two_edition_modelo(
        tmp_path,
        predecessor_grade="filing",
        successor_grade="calculation",
        declare_predecessor=False,
    )

    modelo = load_modelo_directory(modelo_dir)

    assert [casilla.id for casilla in modelo.revisions["2025"].casillas] == ["0004"]
    assert [casilla.id for casilla in modelo.revisions["2024"].casillas] == ["0001", "0002", "0003"]
