"""Loader materialisation of an edition that names its predecessor.

An edition naming a predecessor states only the casillas that are new or that
differ; the loader resolves the rest from the predecessor so every consumer
receives the complete edition. These tests drive the real directory loader over
an on-disk TOML tree and check the properties that make that resolution safe:
a stated row replaces the inherited row carrying its lineage in that row's
position, new rows follow the inherited ones, a retired lineage is dropped, a
chain resolves transitively, an inherited row carries no lineage claim and is
marked with the edition that stated it, and nothing is inherited unless the key
is declared. Every ambiguous shape is refused, and each refusal is paired with the
repaired tree loading.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_support.registry_authoring import load_modelo_directory

from ..errors import RegistryLoadError
from ..modelo_localization import ModeloLocalizationFieldKind, casilla_occurrence_locale_key
from ..schema import ModeloRevision
from ._loader_directory_mode_support import _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "999"
_LEGAL_REF = "ley-58-2003:art-29"
_NO_PREDECESSOR = (
    'predecessor = { none = { reason = "First published edition of this form.", '
    f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str | None, extra: str = "") -> str:
    lineage_line = f'continuidad_id = "{lineage}"\n' if lineage is not None else ""
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f"{lineage_line}"
        f"{extra}"
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n\n'
    )


def _retirement(revision_id: str, *, lineage: str, from_revision: str) -> str:
    return (
        f'[[revisions."{revision_id}".casilla_continuidad_evolutions]]\n'
        f'id = "retire-{lineage}"\n'
        f'continuidad_id = "{lineage}"\n'
        f'from_revision = "{from_revision}"\n'
        f'to_revision = "{revision_id}"\n'
        'evolution_kind = "retired"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    manifest_extra: str = "",
    evolutions: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        (
            f'[revisions."{revision_id}"]\n'
            f"valid_from = {year}-01-01\n"
            f"valid_to = {year}-12-31\n"
            f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n'
            f"{manifest_extra}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    if casillas:
        (revision_dir / "casillas").mkdir()
        (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    if evolutions:
        (revision_dir / "casilla_continuidad_evolutions").mkdir()
        (revision_dir / "casilla_continuidad_evolutions" / "0001-evolutions.toml").write_text(
            evolutions, encoding="utf-8", newline="\n"
        )


def _predecessor_2024(modelo_dir: Path, *, manifest_extra: str = "") -> None:
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        manifest_extra=manifest_extra,
        casillas=(
            _casilla("2024", "0001", number="1", lineage="base-imponible")
            + _casilla("2024", "0002", number="2", lineage="cuota-integra")
            + _casilla("2024", "0003", number="3", lineage="deduccion-retirada")
            + _casilla("2024", "0004", number="4", lineage=None)
        ),
    )


def _modelo_root(root: Path) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def _delta_successor_modelo(root: Path, *, declare_predecessor: bool) -> Path:
    """A 2024 edition and a 2025 edition stating one changed row, one new row and one retirement."""
    modelo_dir = _modelo_root(root)
    _predecessor_2024(modelo_dir)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n' if declare_predecessor else "",
        casillas=(
            _casilla("2025", "0005", number="5", lineage="recargo-nuevo")
            + _casilla("2025", "0002", number="22", lineage="cuota-integra")
        ),
        evolutions=_retirement("2025", lineage="deduccion-retirada", from_revision="2024"),
    )
    return modelo_dir


def _rows(revision: ModeloRevision) -> list[tuple[str, str, str | None]]:
    return [(casilla.id, casilla.number, casilla.continuidad_id) for casilla in revision.casillas]


def test_a_declared_predecessor_is_inherited_with_stated_rows_overriding_by_lineage(tmp_path: Path) -> None:
    """Inherited order holds, the changed row keeps its slot, the retired lineage goes, the new row trails.

    The same tree without the declaration is the teeth: the successor is then a
    full-copy edition holding only what it states, so the inherited rows above
    exist only because the key was declared, never because rows were absent.
    """
    definition = load_modelo_directory(_delta_successor_modelo(tmp_path / "delta", declare_predecessor=True))

    assert _rows(definition.revisions["2025"]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", None),
        ("0005", "5", "recargo-nuevo"),
    ]
    assert _rows(definition.revisions["2024"]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "2", "cuota-integra"),
        ("0003", "3", "deduccion-retirada"),
        ("0004", "4", None),
    ]

    full_copy = load_modelo_directory(_delta_successor_modelo(tmp_path / "full-copy", declare_predecessor=False))
    assert _rows(full_copy.revisions["2025"]) == [
        ("0005", "5", "recargo-nuevo"),
        ("0002", "22", "cuota-integra"),
    ]


def test_an_inherited_row_takes_the_successor_editions_locale_key(tmp_path: Path) -> None:
    """Materialisation runs before enrolment, so no successor row carries a key naming its predecessor."""
    successor = load_modelo_directory(_delta_successor_modelo(tmp_path, declare_predecessor=True)).revisions["2025"]

    inherited = next(casilla for casilla in successor.casillas if casilla.id == "0001")
    assert inherited.localization_keys[0] == casilla_occurrence_locale_key(
        _MODELO_ID, "2025", "0001", ModeloLocalizationFieldKind.LABEL
    )


def test_a_chain_of_predecessors_resolves_transitively(tmp_path: Path) -> None:
    """A third edition inherits what the second inherited, including the second's overrides."""
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    _write_edition(
        modelo_dir,
        "2026",
        year=2026,
        manifest_extra='predecessor = "2025"\n',
        casillas=_casilla("2026", "0001", number="11", lineage="base-imponible"),
    )

    assert _rows(load_modelo_directory(modelo_dir).revisions["2026"]) == [
        ("0001", "11", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", None),
        ("0005", "5", "recargo-nuevo"),
    ]


def test_every_inherited_row_is_marked_with_the_edition_that_last_stated_it(tmp_path: Path) -> None:
    """The marker follows the edition that stated the row, down the chain, and a stated row carries none."""
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    _write_edition(
        modelo_dir,
        "2026",
        year=2026,
        manifest_extra='predecessor = "2025"\n',
        casillas=_casilla("2026", "0001", number="11", lineage="base-imponible"),
    )
    definition = load_modelo_directory(modelo_dir)

    def marks(revision_id: str) -> list[tuple[str, str | None]]:
        return [(casilla.id, casilla.inherited_from) for casilla in definition.revisions[revision_id].casillas]

    assert marks("2024") == [("0001", None), ("0002", None), ("0003", None), ("0004", None)]
    assert marks("2025") == [("0001", "2024"), ("0002", None), ("0004", "2024"), ("0005", None)]
    assert marks("2026") == [("0001", None), ("0002", "2025"), ("0004", "2024"), ("0005", "2025")]
    # Where a row is stated is not what it means, so the marker never serialises.
    assert all("inherited_from" not in row for row in definition.revisions["2026"].model_dump()["casillas"])


def test_an_authored_inheritance_marker_is_refused_and_the_repaired_tree_loads(tmp_path: Path) -> None:
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    fragment = modelo_dir / "revisions" / "2024" / "casillas" / "0001-casillas.toml"
    repaired = fragment.read_text(encoding="utf-8")
    fragment.write_text(
        repaired.replace('number = "1"\n', 'number = "1"\ninherited_from = "2023"\n', 1), encoding="utf-8", newline="\n"
    )

    with pytest.raises(RegistryLoadError, match=r"revision '2024': casillas \['0001'\] author inherited_from"):
        load_modelo_directory(modelo_dir)

    fragment.write_text(repaired, encoding="utf-8", newline="\n")
    assert load_modelo_directory(modelo_dir).revisions["2025"].casillas[0].inherited_from == "2024"


_EVIDENCE = "Diseño de registro 2024, campo 1: casilla nueva en el formulario."


def test_an_inherited_row_never_carries_its_predecessors_lineage_claims(tmp_path: Path) -> None:
    """A claim that a box is new on its form is false one edition later, so inheriting drops it.

    The predecessor still carries both claims, so their absence on the
    successor is the merge's doing; a superseding row keeps the claims it
    states itself.
    """
    modelo_dir = _modelo_root(tmp_path)
    claims = f'continuidad_origin = "new_on_form"\ncontinuidad_evidence = "{_EVIDENCE}"\n'
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=(
            _casilla("2024", "0001", number="1", lineage="base-imponible", extra=claims)
            + _casilla("2024", "0002", number="2", lineage="cuota-integra", extra=claims)
        ),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0002", number="22", lineage="cuota-integra", extra=claims),
    )
    definition = load_modelo_directory(modelo_dir)

    def claimed(revision_id: str) -> list[tuple[str, str | None, str | None]]:
        return [
            (casilla.id, casilla.continuidad_origin, casilla.continuidad_evidence)
            for casilla in definition.revisions[revision_id].casillas
        ]

    assert claimed("2024") == [("0001", "new_on_form", _EVIDENCE), ("0002", "new_on_form", _EVIDENCE)]
    assert claimed("2025") == [("0001", None, None), ("0002", "new_on_form", _EVIDENCE)]


def test_an_edition_declaring_no_predecessor_inherits_nothing(tmp_path: Path) -> None:
    modelo_dir = _modelo_root(tmp_path)
    _predecessor_2024(modelo_dir)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra=_NO_PREDECESSOR,
        casillas=_casilla("2025", "0009", number="9", lineage="variante"),
    )

    assert _rows(load_modelo_directory(modelo_dir).revisions["2025"]) == [("0009", "9", "variante")]


@pytest.mark.parametrize(
    ("stated", "refusal"),
    [
        pytest.param(
            _casilla("2025", "0001", number="1", lineage="otro-concepto"),
            r"stated casilla '0001' of lineage 'otro-concepto' collides with the inherited casilla '0001' "
            r"of lineage 'base-imponible'",
            id="undeclared-repurpose",
        ),
        pytest.param(
            _casilla("2025", "0004", number="4", lineage=None),
            r"stated casilla '0004' of lineage \(none declared\) collides with the inherited casilla '0004' "
            r"of lineage \(none declared\)",
            id="collision-without-lineage",
        ),
        pytest.param(
            _casilla("2025", "0007", number="7", lineage="cuota-integra")
            + _casilla("2025", "0008", number="8", lineage="cuota-integra"),
            r"states more than one casilla of lineage 'cuota-integra'",
            id="two-stated-rows-one-lineage",
        ),
        pytest.param(
            _casilla("2025", "0003", number="3", lineage="deduccion-retirada"),
            r"states a casilla of lineage 'deduccion-retirada', which the same edition retires",
            id="stated-and-retired",
        ),
    ],
)
def test_an_ambiguous_override_is_refused_and_the_repaired_tree_loads(
    tmp_path: Path, stated: str, refusal: str
) -> None:
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    fragment = modelo_dir / "revisions" / "2025" / "casillas" / "0001-casillas.toml"
    repaired = fragment.read_text(encoding="utf-8")
    fragment.write_text(repaired + stated, encoding="utf-8", newline="\n")

    with pytest.raises(RegistryLoadError, match=rf"revision '2025' inheriting from '2024': {refusal}"):
        load_modelo_directory(modelo_dir)

    fragment.write_text(repaired, encoding="utf-8", newline="\n")
    assert [casilla.id for casilla in load_modelo_directory(modelo_dir).revisions["2025"].casillas] == [
        "0001",
        "0002",
        "0004",
        "0005",
    ]


def test_a_predecessor_carrying_one_lineage_twice_cannot_be_superseded(tmp_path: Path) -> None:
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=(
            _casilla("2024", "0001", number="1", lineage="repetida")
            + _casilla("2024", "0002", number="2", lineage="repetida")
        ),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0001", number="10", lineage="repetida"),
    )

    with pytest.raises(RegistryLoadError, match=r"carries lineage \['repetida'\] on more than one row"):
        load_modelo_directory(modelo_dir)


def test_a_predecessor_cycle_is_refused_before_anything_is_inherited(tmp_path: Path) -> None:
    """The forest check runs on the raw declarations, so a cycle never reaches the recursion."""
    modelo_dir = _modelo_root(tmp_path)
    _predecessor_2024(modelo_dir, manifest_extra='predecessor = "2025"\n')
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    with pytest.raises(RegistryLoadError, match="predecessor declarations form a cycle"):
        load_modelo_directory(modelo_dir)
