"""A declared predecessor must start before a successor it does not overlap.

Each refusal is proven in both directions on the same on-disk tree: the plant
refuses the load, the repair loads, and re-planting refuses again. The tests
drive the real directory loader, so the rule is exercised where a modelo is
validated after its delta editions materialise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.revision_contracts import (
    DeclaredPredecessor,
    RevisionWindow,
    validate_predecessor_date_agreement,
)
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-29"
# Two consecutive exercises of the support envelope stand in for an earlier and a later edition.
_EARLIER, _LATER = filing_year_envelope().years[-2:]


@dataclass(frozen=True, slots=True)
class _Edition:
    revision_id: str
    valid_from: str
    years: tuple[int, ...]
    casilla: str
    predecessor: str | None = None


def _write_edition(modelo_dir: Path, edition: _Edition) -> None:
    revision_dir = modelo_dir / "revisions" / edition.revision_id
    (revision_dir / "casillas").mkdir(parents=True, exist_ok=True)
    years = ", ".join(str(year) for year in edition.years)
    predecessor = f'predecessor = "{edition.predecessor}"\n' if edition.predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        (
            f'[revisions."{edition.revision_id}"]\n'
            f"valid_from = {edition.valid_from}\n"
            f'period_selector = {{ years = [{years}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
            f"{predecessor}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        (
            f'[[revisions."{edition.revision_id}".casillas]]\n'
            f'id = "{edition.casilla}"\n'
            f'number = "{edition.casilla}"\n'
            'section = ["liquidacion"]\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
        ),
        encoding="utf-8",
        newline="\n",
    )


def _write_editions(root: Path, *editions: _Edition) -> Path:
    modelo_dir = root / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    for edition in editions:
        _write_edition(modelo_dir, edition)
    return modelo_dir


_BACKWARDS = re.escape(
    f"revision '{_EARLIER}' (valid {_EARLIER}-01-01 to open; years {_EARLIER}; periods 0A) declares predecessor "
) + (
    re.escape(
        f"'{_LATER}' (valid {_LATER}-01-01 to open; years {_LATER}; periods 0A), which does not take effect before it"
    )
)


def test_a_successor_naming_a_later_non_overlapping_edition_is_refused_naming_both(tmp_path: Path) -> None:
    """The backwards edge refuses with both editions and their windows; turning it round loads."""
    modelo_dir = _write_editions(
        tmp_path,
        _Edition(str(_EARLIER), f"{_EARLIER}-01-01", (_EARLIER,), "01", predecessor=str(_LATER)),
        _Edition(str(_LATER), f"{_LATER}-01-01", (_LATER,), "02"),
    )
    with pytest.raises(RegistryLoadError, match=_BACKWARDS):
        load_modelo_directory(modelo_dir)

    _write_edition(modelo_dir, _Edition(str(_EARLIER), f"{_EARLIER}-01-01", (_EARLIER,), "01"))
    _write_edition(modelo_dir, _Edition(str(_LATER), f"{_LATER}-01-01", (_LATER,), "02", predecessor=str(_EARLIER)))
    repaired = load_modelo_directory(modelo_dir)
    assert repaired.revisions[str(_LATER)].predecessor == DeclaredPredecessor(revision_id=str(_EARLIER))

    _write_edition(modelo_dir, _Edition(str(_EARLIER), f"{_EARLIER}-01-01", (_EARLIER,), "01", predecessor=str(_LATER)))
    _write_edition(modelo_dir, _Edition(str(_LATER), f"{_LATER}-01-01", (_LATER,), "02"))
    with pytest.raises(RegistryLoadError, match=_BACKWARDS):
        load_modelo_directory(modelo_dir)


def test_an_overlapping_pair_is_exempt_whichever_way_the_edge_points(tmp_path: Path) -> None:
    """Editions sharing a live window have no date order, so a later-starting predecessor loads."""
    modelo_dir = _write_editions(
        tmp_path,
        _Edition("variante-a", f"{_EARLIER}-01-01", (_EARLIER, _LATER), "01", predecessor="variante-b"),
        _Edition("variante-b", f"{_LATER}-01-01", (_LATER,), "02"),
    )
    loaded = load_modelo_directory(modelo_dir)
    assert loaded.revisions["variante-a"].predecessor == DeclaredPredecessor(revision_id="variante-b")

    _write_edition(modelo_dir, _Edition("variante-a", f"{_EARLIER}-01-01", (_EARLIER,), "01", predecessor="variante-b"))
    with pytest.raises(RegistryLoadError, match="does not take effect before it"):
        load_modelo_directory(modelo_dir)


def _window(valid_from: date, *years: int, periods: tuple[str, ...] = ("0A",)) -> RevisionWindow:
    return RevisionWindow(
        valid_from=valid_from,
        valid_to=None,
        period_selector=PeriodSelector(years=years, periods=periods),
    )


def test_a_same_day_non_overlapping_predecessor_is_not_earlier() -> None:
    """Disjoint periods with one start date give no order for the edge to agree with."""
    windows = {
        "mensual": _window(date(_LATER, 1, 1), _LATER, periods=("01",)),
        "anual": _window(date(_LATER, 1, 1), _LATER, periods=("0A",)),
    }
    with pytest.raises(RegistryValidationError, match=r"revision 'mensual' .* declares predecessor 'anual'"):
        validate_predecessor_date_agreement("999", named={"mensual": "anual"}, windows=windows)

    earlier = {**windows, "anual": _window(date(_EARLIER, 1, 1), _LATER, periods=("0A",))}
    validate_predecessor_date_agreement("999", named={"mensual": "anual"}, windows=earlier)


def test_an_edge_to_an_edition_without_a_window_is_refused_not_crashed() -> None:
    windows = {str(_LATER): _window(date(_LATER, 1, 1), _LATER)}
    with pytest.raises(RegistryValidationError, match=f"revision '{_EARLIER}' has no declared validity window"):
        validate_predecessor_date_agreement("999", named={str(_LATER): str(_EARLIER)}, windows=windows)
