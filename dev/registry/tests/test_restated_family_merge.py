"""The keyed merge honours an edition's authored restatement of a family.

``restated_families`` is the edition saying that the official structure it was
drawn from lays a family out end to end: the members it does not repeat are
withdrawn by that document rather than unchanged, so inheriting them would
carry into the edition rows nobody established for it. The merge answers the
declaration by not merging the family at all -- the stated array survives as
authored, member for member and in stated order.

The declaration is per family and per edge. Every other keyed family of the
declaring edition inherits exactly as before, which is what the sibling-family
test holds, and the control test loads the same fixture without the
declaration to show the merge really does inherit and reorder there: without
it, the first test would pass on a fixture that never exercised inheritance.

Every test drives the real directory loader over an on-disk two-edition modelo
built in ``tmp_path``. Nothing is mocked; a double would verify the double.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_LEGAL_REF: Final = "ley-58-2003:art-29"
_SOURCE_REF: Final = "aeat-manual"
_PREDECESSOR: Final = "2024"
_SUCCESSOR: Final = "2025"
_REASON: Final = "the 2025 diseno de registros lays the formula set out end to end"
_RESTATED_FORMULAS: Final = (
    f'restated_families = [{{ family = "formulas", cause = "official_structure_differs", reason = "{_REASON}" }}]\n'
)
_BASE_FORMULA: Final = "modelo-999-base"
_CUOTA_FORMULA: Final = "modelo-999-cuota"
_RECARGO_FORMULA: Final = "modelo-999-recargo"


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _formula(revision_id: str, formula_id: str, *, target: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _construct(revision_id: str, construct_id: str, *, casilla_id: str) -> str:
    return (
        f'[[revisions."{revision_id}".constructs]]\n'
        f'id = "{construct_id}"\n'
        f'casilla_ids = ["{casilla_id}"]\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _write_revision(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    formulas: str,
    constructs: str,
    predecessor: str | None = None,
    extra_manifest: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f"{predecessor_line}{extra_manifest}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas").mkdir()
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    (revision_dir / "formulas").mkdir()
    (revision_dir / "formulas" / "0001-formulas.toml").write_text(formulas, encoding="utf-8", newline="\n")
    if constructs:
        (revision_dir / "constructs").mkdir()
        (revision_dir / "constructs" / "0001-constructs.toml").write_text(constructs, encoding="utf-8", newline="\n")


def _build_modelo(root: Path, *, successor_extra: str = "") -> Path:
    """A 2024 root and a 2025 delta whose stated formulas are fewer and reordered.

    The predecessor states three formulas in target order; the successor
    restates two of them in the opposite order and states neither the third nor
    the predecessor's construct. Inheritance and restatement therefore differ in
    both membership and order, which is what makes the two readings separable.
    """
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_revision(
        modelo_dir,
        _PREDECESSOR,
        year=2024,
        casillas=(
            _casilla(_PREDECESSOR, "0001", number="1", lineage="base")
            + _casilla(_PREDECESSOR, "0002", number="2", lineage="cuota")
            + _casilla(_PREDECESSOR, "0003", number="3", lineage="recargo")
        ),
        formulas=(
            _formula(_PREDECESSOR, _BASE_FORMULA, target="0001")
            + _formula(_PREDECESSOR, _CUOTA_FORMULA, target="0002")
            + _formula(_PREDECESSOR, _RECARGO_FORMULA, target="0003")
        ),
        constructs=_construct(_PREDECESSOR, "modelo-999-liquidacion", casilla_id="0001"),
    )
    _write_revision(
        modelo_dir,
        _SUCCESSOR,
        year=2025,
        predecessor=_PREDECESSOR,
        casillas=_casilla(_SUCCESSOR, "0002", number="22", lineage="cuota"),
        formulas=(
            _formula(_SUCCESSOR, _RECARGO_FORMULA, target="0003") + _formula(_SUCCESSOR, _BASE_FORMULA, target="0001")
        ),
        constructs=_construct(_SUCCESSOR, "modelo-999-recargo-equivalencia", casilla_id="0002"),
        extra_manifest=successor_extra,
    )
    return modelo_dir


def _successor(modelo_dir: Path) -> ModeloRevision:
    return load_modelo_directory(modelo_dir).revisions[_SUCCESSOR]


def test_a_restated_family_materialises_to_the_edition_s_stated_array(tmp_path: Path) -> None:
    """The declared family is exactly what the edition states: same members, same order.

    Nothing is inherited into it -- the predecessor's ``cuota`` formula is gone
    -- and nothing is reordered, so the array reads as the official structure
    laid it out.
    """
    revision = _successor(_build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

    assert tuple(formula.id for formula in revision.formulas) == (_RECARGO_FORMULA, _BASE_FORMULA)
    assert tuple(formula.target_casilla_id for formula in revision.formulas) == ("0003", "0001")


def test_without_the_declaration_the_same_fixture_inherits_and_reorders(tmp_path: Path) -> None:
    """The control: the merge really does add and reorder members here.

    Same two editions, same stated formulas, no restatement claim. The
    predecessor's third formula survives and the successor's stated order is
    replaced by the predecessor's, which is precisely what the declaration
    withdraws.
    """
    revision = _successor(_build_modelo(tmp_path))

    assert tuple(formula.id for formula in revision.formulas) == (
        _BASE_FORMULA,
        _CUOTA_FORMULA,
        _RECARGO_FORMULA,
    )


def test_a_sibling_family_of_the_declaring_edition_still_inherits(tmp_path: Path) -> None:
    """The claim is per family: constructs are undeclared, so they merge as before."""
    revision = _successor(_build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

    assert tuple(construct.id for construct in revision.constructs) == (
        "modelo-999-liquidacion",
        "modelo-999-recargo-equivalencia",
    )


def test_restating_a_family_the_edition_states_empty_is_refused_before_the_merge(tmp_path: Path) -> None:
    """A family with no stated members never reaches the merge; the schema refuses the edition.

    ``parameters`` is a keyed family neither edition declares, so restating it
    withdraws nothing while reading as though it did. The refusal is the
    declaration's own validator, not a merge behaviour, and the merge relies on
    it: a family it skipped on an edition that states nothing would silently
    empty the family instead.
    """
    empty_family = (
        'restated_families = [{ family = "parameters", cause = "official_structure_differs", '
        f'reason = "{_REASON}" }}]\n'
    )

    with pytest.raises(RegistryValidationError, match="restated in full but declares no 'parameters'"):
        load_modelo_directory(_build_modelo(tmp_path, successor_extra=empty_family))


@pytest.mark.parametrize(
    ("base_id", "cuota_id", "target", "accepted"),
    [
        ("0011", "0002", "0011", True),
        ("0011", "0002", "0002", False),
        ("0002", "0001", "0001", False),
        ("0011", "0002", "0099", False),
    ],
    ids=("renumbered-concept", "different-concept", "reused-number", "absent-target"),
)
def test_formula_target_identity_follows_unique_casilla_continuity(
    tmp_path: Path,
    base_id: str,
    cuota_id: str,
    target: str,
    *,
    accepted: bool,
) -> None:
    """A target renumbering preserves identity; a reused number does not."""
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Test")
    _write_revision(
        modelo_dir,
        _PREDECESSOR,
        year=2024,
        casillas=(
            _casilla(_PREDECESSOR, "0001", number="1", lineage="base")
            + _casilla(_PREDECESSOR, "0002", number="2", lineage="cuota")
        ),
        formulas=_formula(_PREDECESSOR, _BASE_FORMULA, target="0001"),
        constructs="",
    )
    _write_revision(
        modelo_dir,
        _SUCCESSOR,
        year=2025,
        predecessor=_PREDECESSOR,
        casillas=(
            _casilla(_SUCCESSOR, base_id, number=base_id, lineage="base")
            + _casilla(_SUCCESSOR, cuota_id, number=cuota_id, lineage="cuota")
        ),
        formulas=_formula(_SUCCESSOR, _BASE_FORMULA, target=target),
        constructs="",
    )
    if accepted:
        revision = _successor(modelo_dir)
        assert revision.formulas[0].target_casilla_id == target
        assert next(row for row in revision.casillas if row.id == target).continuidad_id == "base"
    else:
        with pytest.raises(RegistryLoadError, match="a change to a field carrying the member's identity"):
            _successor(modelo_dir)
