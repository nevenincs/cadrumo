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

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_family_delta_collapse import collapse_keyed_families
from .synthetic_delta_edition_support import (
    LEGAL_REF,
    MODELO_ID,
    PREDECESSOR_EDITION,
    PREDECESSOR_EDITION_YEAR,
    SOURCE_REF,
    SUCCESSOR_EDITION,
    SUCCESSOR_EDITION_YEAR,
    delta_casilla,
    delta_formula,
    write_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REASON: Final = "the 2025 diseno de registros lays the formula set out end to end"
_RESTATED_FORMULAS: Final = (
    f'restated_families = [{{ family = "formulas", cause = "official_structure_differs", reason = "{_REASON}" }}]\n'
)
BASE_FORMULA: Final = "modelo-999-base"
CUOTA_FORMULA: Final = "modelo-999-cuota"
RECARGO_FORMULA: Final = "modelo-999-recargo"
_THIRD_EDITION_YEAR: Final = SUCCESSOR_EDITION_YEAR + 1
_THIRD_EDITION: Final = str(_THIRD_EDITION_YEAR)


def _construct(revision_id: str, construct_id: str, *, casilla_id: str) -> str:
    return (
        f'[[revisions."{revision_id}".constructs]]\n'
        f'id = "{construct_id}"\n'
        f'casilla_ids = ["{casilla_id}"]\n'
        f'legal_refs = ["{LEGAL_REF}"]\n'
        f'source_refs = ["{SOURCE_REF}"]\n\n'
    )


def build_modelo(root: Path, *, successor_extra: str = "") -> Path:
    """A 2024 root and a 2025 delta whose stated formulas are fewer and reordered.

    The predecessor states three formulas in target order; the successor
    restates two of them in the opposite order and states neither the third nor
    the predecessor's construct. Inheritance and restatement therefore differ in
    both membership and order, which is what makes the two readings separable.
    """
    modelo_dir = root / MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    write_revision(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=(
            delta_casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base")
            + delta_casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota")
            + delta_casilla(PREDECESSOR_EDITION, "0003", number="3", lineage="recargo")
        ),
        formulas=(
            delta_formula(PREDECESSOR_EDITION, BASE_FORMULA, target="0001")
            + delta_formula(PREDECESSOR_EDITION, CUOTA_FORMULA, target="0002")
            + delta_formula(PREDECESSOR_EDITION, RECARGO_FORMULA, target="0003")
        ),
        constructs=_construct(PREDECESSOR_EDITION, "modelo-999-liquidacion", casilla_id="0001"),
    )
    write_revision(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        predecessor=PREDECESSOR_EDITION,
        casillas=delta_casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota"),
        formulas=(
            delta_formula(SUCCESSOR_EDITION, RECARGO_FORMULA, target="0003")
            + delta_formula(SUCCESSOR_EDITION, BASE_FORMULA, target="0001")
        ),
        constructs=_construct(SUCCESSOR_EDITION, "modelo-999-recargo-equivalencia", casilla_id="0002"),
        extra_manifest=successor_extra,
    )
    return modelo_dir


def _successor(modelo_dir: Path) -> ModeloRevision:
    return load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION]


def test_a_restated_family_materialises_to_the_edition_s_stated_array(tmp_path: Path) -> None:
    """The declared family is exactly what the edition states: same members, same order.

    Nothing is inherited into it -- the predecessor's ``cuota`` formula is gone
    -- and nothing is reordered, so the array reads as the official structure
    laid it out.
    """
    revision = _successor(build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

    assert tuple(formula.id for formula in revision.formulas) == (RECARGO_FORMULA, BASE_FORMULA)
    assert tuple(formula.target_casilla_id for formula in revision.formulas) == ("0003", "0001")


def test_without_the_declaration_the_same_fixture_inherits_and_reorders(tmp_path: Path) -> None:
    """The control: the merge really does add and reorder members here.

    Same two editions, same stated formulas, no restatement claim. The
    predecessor's third formula survives and the successor's stated order is
    replaced by the predecessor's, which is precisely what the declaration
    withdraws.
    """
    revision = _successor(build_modelo(tmp_path))

    assert tuple(formula.id for formula in revision.formulas) == (
        BASE_FORMULA,
        CUOTA_FORMULA,
        RECARGO_FORMULA,
    )


def test_a_sibling_family_of_the_declaring_edition_still_inherits(tmp_path: Path) -> None:
    """The claim is per family: constructs are undeclared, so they merge as before."""
    revision = _successor(build_modelo(tmp_path, successor_extra=_RESTATED_FORMULAS))

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

    with pytest.raises(RegistryLoadError, match="restated in full but declares no 'parameters'"):
        load_modelo_directory(build_modelo(tmp_path, successor_extra=empty_family))


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
    modelo_dir = tmp_path / MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Test")
    write_revision(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=(
            delta_casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base")
            + delta_casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota")
        ),
        formulas=delta_formula(PREDECESSOR_EDITION, BASE_FORMULA, target="0001"),
        constructs="",
    )
    write_revision(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        predecessor=PREDECESSOR_EDITION,
        casillas=(
            delta_casilla(SUCCESSOR_EDITION, base_id, number=base_id, lineage="base")
            + delta_casilla(SUCCESSOR_EDITION, cuota_id, number=cuota_id, lineage="cuota")
        ),
        formulas=delta_formula(SUCCESSOR_EDITION, BASE_FORMULA, target=target),
        constructs="",
    )
    if accepted:
        revision = _successor(modelo_dir)
        assert revision.formulas[0].target_casilla_id == target
        assert next(row for row in revision.casillas if row.id == target).continuidad_id == "base"
    else:
        with pytest.raises(RegistryLoadError, match="a change to a field carrying the member's identity"):
            _successor(modelo_dir)


def test_omitted_formula_cannot_inherit_onto_reused_split_child(tmp_path: Path) -> None:
    from .test_casilla_structural_succession import casilla_structural_succession_relation

    modelo_dir = tmp_path / MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Structural formula identity")
    write_revision(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=delta_casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="combined"),
        formulas=delta_formula(PREDECESSOR_EDITION, BASE_FORMULA, target="0001"),
        constructs="",
    )
    write_revision(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        predecessor=PREDECESSOR_EDITION,
        casillas=delta_casilla(SUCCESSOR_EDITION, "0001", number="1", lineage="surname")
        + delta_casilla(SUCCESSOR_EDITION, "0002", number="2", lineage="given"),
        formulas=f'[revisions."{SUCCESSOR_EDITION}"]\nformulas = []\n',
        constructs="",
    )
    directory = modelo_dir / "revisions" / SUCCESSOR_EDITION / "casilla_structural_successions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(casilla_structural_succession_relation(), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="a change to a field carrying the member's identity"):
        load_modelo_directory(modelo_dir)


@pytest.mark.parametrize("lineage", [None, "stable"])
def test_omitted_formula_keeps_unchanged_target_with_or_without_lineage(tmp_path: Path, lineage: str | None) -> None:
    modelo_dir = tmp_path / MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Unchanged formula identity")
    for year in (PREDECESSOR_EDITION_YEAR, SUCCESSOR_EDITION_YEAR):
        row = delta_casilla(str(year), "0001", number="1", lineage=lineage or "unused")
        if lineage is None:
            row = row.replace('continuidad_id = "unused"\n', "")
        if year == SUCCESSOR_EDITION_YEAR:
            row = f'[revisions."{SUCCESSOR_EDITION}"]\ncasillas = []\n'
        write_revision(
            modelo_dir,
            str(year),
            year=year,
            predecessor=PREDECESSOR_EDITION if year == SUCCESSOR_EDITION_YEAR else None,
            casillas=row,
            formulas=delta_formula(PREDECESSOR_EDITION, BASE_FORMULA, target="0001")
            if year == PREDECESSOR_EDITION_YEAR
            else f'[revisions."{SUCCESSOR_EDITION}"]\nformulas = []\n',
            constructs="",
        )
    assert _successor(modelo_dir).formulas[0].target_casilla_id == "0001"


@pytest.mark.parametrize("stated", ["omitted", "identical", "explicit-default"])
@pytest.mark.parametrize(
    "expression",
    [
        '{ casilla_id = "0001" }',
        '{ op = "add", args = [{ literal = "0" }, { op = "add", args = '
        '[{ casilla_id = "0001" }, { literal = "0" }] }] }',
    ],
    ids=["direct", "nested"],
)
def test_unchanged_formula_operand_cannot_follow_reused_split_child(
    tmp_path: Path, *, stated: str, expression: str
) -> None:
    from .test_casilla_structural_succession import casilla_structural_succession_relation

    modelo_dir = tmp_path / MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Structural operand identity")
    for year in (PREDECESSOR_EDITION_YEAR, SUCCESSOR_EDITION_YEAR):
        revision = str(year)
        rows = delta_casilla(revision, "0003", number="3", lineage="total")
        rows += (
            delta_casilla(revision, "0001", number="1", lineage="combined")
            if year == PREDECESSOR_EDITION_YEAR
            else delta_casilla(revision, "0001", number="1", lineage="surname")
            + delta_casilla(revision, "0002", number="2", lineage="given")
        )
        formulas = delta_formula(revision, BASE_FORMULA, target="0003").replace('{ literal = "0" }', expression)
        if year == SUCCESSOR_EDITION_YEAR and stated == "explicit-default":
            formulas = formulas.replace('casilla_id = "0001"', 'casilla_id = "0001", args = []')
        write_revision(
            modelo_dir,
            revision,
            year=year,
            predecessor=PREDECESSOR_EDITION if year == SUCCESSOR_EDITION_YEAR else None,
            casillas=rows,
            formulas=formulas
            if year == PREDECESSOR_EDITION_YEAR or stated != "omitted"
            else f'[revisions."{SUCCESSOR_EDITION}"]\nformulas = []\n',
            constructs="",
        )
    directory = modelo_dir / "revisions" / SUCCESSOR_EDITION / "casilla_structural_successions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(casilla_structural_succession_relation(), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="unchanged expression whose casilla operand"):
        load_modelo_directory(modelo_dir)


@pytest.mark.parametrize("changed", [False, True], ids=["unchanged", "explicit-new-expression"])
def test_formula_operand_identity_preserves_valid_declarations(tmp_path: Path, *, changed: bool) -> None:
    modelo_dir = tmp_path / MODELO_ID
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Declared operand identity")
    for year in (PREDECESSOR_EDITION_YEAR, SUCCESSOR_EDITION_YEAR, _THIRD_EDITION_YEAR):
        revision = str(year)
        expression = (
            '{ casilla_id = "0002" }' if changed and year > PREDECESSOR_EDITION_YEAR else '{ casilla_id = "0001" }'
        )
        write_revision(
            modelo_dir,
            revision,
            year=year,
            predecessor=str(year - 1) if year > PREDECESSOR_EDITION_YEAR else None,
            casillas="".join(
                delta_casilla(revision, number, number=number, lineage=lineage)
                for number, lineage in (("0001", "base"), ("0002", "cuota"), ("0003", "total"))
            ),
            formulas=delta_formula(revision, BASE_FORMULA, target="0003").replace('{ literal = "0" }', expression)
            if year == PREDECESSOR_EDITION_YEAR or (changed and year == SUCCESSOR_EDITION_YEAR)
            else f'[revisions."{revision}"]\nformulas = []\n',
            constructs="",
        )
    modelo = load_modelo_directory(modelo_dir)
    assert modelo.revisions[_THIRD_EDITION].formulas[0].expression.casilla_id == ("0002" if changed else "0001")


def test_collapsing_a_restated_family_lifts_the_restatement_without_losing_members(tmp_path: Path) -> None:
    """The family collapse turns a restatement into the ordinary delta, member for member.

    A restated family inherits nothing, so dropping its members while leaving the
    declaration in place would delete them; the collapse must lift the
    declaration and state the predecessor-only member as an explicit removal.
    """
    source = build_modelo(tmp_path / "source", successor_extra=_RESTATED_FORMULAS)
    candidate = tmp_path / "candidate" / MODELO_ID

    collapse_keyed_families(source, candidate)

    manifest = (candidate / "revisions" / SUCCESSOR_EDITION / "revision.toml").read_text(encoding="utf-8")
    assert "restated_families" not in manifest
    assert "family_removals" in manifest
    assert _successor(candidate).formulas == _successor(source).formulas
