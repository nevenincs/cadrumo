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
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_overrides import CasillaFieldOverride

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from .synthetic_delta_edition_support import (
    PREDECESSOR_EDITION,
    PREDECESSOR_EDITION_YEAR,
    SUCCESSOR_EDITION,
    SUCCESSOR_EDITION_YEAR,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "999"
# A chain of up to four consecutive editions: one before the predecessor, and one after the successor.
_EARLIER_EDITION_YEAR = PREDECESSOR_EDITION_YEAR - 1
_EARLIER_EDITION = str(_EARLIER_EDITION_YEAR)
_THIRD_EDITION_YEAR = SUCCESSOR_EDITION_YEAR + 1
_THIRD_EDITION = str(_THIRD_EDITION_YEAR)
_LEGAL_REF = "ley-58-2003:art-29"
_NO_PREDECESSOR = (
    'predecessor = { none = { reason = "First published edition of this form.", '
    f'legal_refs = ["{_LEGAL_REF}"], source_refs = ["aeat-manual"] }} }}\n'
)


def casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str | None, extra: str = "") -> str:
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


def retirement(revision_id: str, *, lineage: str, from_revision: str) -> str:
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


def write_edition(
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


def _predecessor_edition(modelo_dir: Path, *, manifest_extra: str = "") -> None:
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        manifest_extra=manifest_extra,
        casillas=(
            casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base-imponible")
            + casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota-integra")
            + casilla(PREDECESSOR_EDITION, "0003", number="3", lineage="deduccion-retirada")
            + casilla(PREDECESSOR_EDITION, "0004", number="4", lineage=None)
        ),
    )


def modelo_root(root: Path) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def _delta_successor_modelo(root: Path, *, declare_predecessor: bool) -> Path:
    """A 2024 edition and a 2025 edition stating one changed row, one new row and one retirement."""
    modelo_dir = modelo_root(root)
    _predecessor_edition(modelo_dir)
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{PREDECESSOR_EDITION}"\n' if declare_predecessor else "",
        casillas=(
            casilla(SUCCESSOR_EDITION, "0005", number="5", lineage="recargo-nuevo")
            + casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota-integra")
        ),
        evolutions=retirement(SUCCESSOR_EDITION, lineage="deduccion-retirada", from_revision=PREDECESSOR_EDITION),
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

    assert _rows(definition.revisions[SUCCESSOR_EDITION]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", None),
        ("0005", "5", "recargo-nuevo"),
    ]
    assert _rows(definition.revisions[PREDECESSOR_EDITION]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "2", "cuota-integra"),
        ("0003", "3", "deduccion-retirada"),
        ("0004", "4", None),
    ]

    full_copy = load_modelo_directory(_delta_successor_modelo(tmp_path / "full-copy", declare_predecessor=False))
    assert _rows(full_copy.revisions[SUCCESSOR_EDITION]) == [
        ("0005", "5", "recargo-nuevo"),
        ("0002", "22", "cuota-integra"),
    ]


def test_field_delta_distinguishes_inherit_delete_and_meaningful_empty_false_zero(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=(
            casilla(
                PREDECESSOR_EDITION,
                "0001",
                number="1",
                lineage=None,
                extra=(
                    'segmento = "DP99901"\nrequired = true\n'
                    f'constraints = {{ min_value = "1", legal_refs = ["{_LEGAL_REF}"], '
                    'source_refs = ["aeat-manual"] }\n'
                ),
            )
            + casilla(PREDECESSOR_EDITION, "0002", number="2", lineage=None)
        ),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=(
            f'predecessor = "{PREDECESSOR_EDITION}"\n'
            f'[[revisions."{SUCCESSOR_EDITION}".casilla_overrides]]\n'
            f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0001" }}\n'
            'fields = { source_refs = ["aeat-form"], section = [], required = false, '
            f'constraints = {{ min_value = "0", legal_refs = ["{_LEGAL_REF}"], '
            'source_refs = ["aeat-manual"] } }\n'
            'removed_fields = ["segmento"]\n'
            f'[[revisions."{SUCCESSOR_EDITION}".casilla_removals]]\n'
            f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0002" }}\n'
        ),
        casillas=casilla(SUCCESSOR_EDITION, "0003", number="3", lineage=None),
    )

    successor = load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION]

    assert [casilla.id for casilla in successor.casillas] == ["0001", "0003"]
    patched = successor.casillas[0]
    assert patched.number == "1"  # omitted override inherits
    assert patched.source_refs == ("aeat-form",)
    assert patched.section == ()
    assert patched.required is False
    assert patched.constraints is not None and patched.constraints.min_value == 0
    assert patched.segmento is None  # explicit field deletion reaches the schema default


def test_field_delta_removes_a_nested_constraint_storage_field(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        manifest_extra='casilla_source_refs = ["aeat-old"]\n',
        casillas=casilla(
            PREDECESSOR_EDITION,
            "0001",
            number="1",
            lineage=None,
            extra=(
                f'constraints = {{ sign = "non_negative", legal_refs = ["{_LEGAL_REF}"], '
                'additional_source_refs = ["boe-form"] }\n'
            ),
        ),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=(
            f'predecessor = "{PREDECESSOR_EDITION}"\n'
            f'[[revisions."{SUCCESSOR_EDITION}".casilla_overrides]]\n'
            f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0001" }}\n'
            'fields = { constraints = { source_refs = ["aeat-new", "boe-form"] } }\n'
            'removed_fields = ["constraints.additional_source_refs"]\n'
        ),
        casillas="",
    )

    patched = load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION].casillas[0]

    assert patched.constraints is not None
    assert patched.constraints.source_refs == ("aeat-new", "boe-form")


@pytest.mark.parametrize(
    ("fields", "removed"),
    (
        ({}, "constraints.additional_source_refs.extra"),
        ({}, "constraints.unknown"),
        ({"constraints": {"source_refs": ["aeat-new"]}}, "constraints.source_refs"),
    ),
)
def test_nested_constraint_removal_contract_fails_closed(fields: object, removed: str) -> None:
    with pytest.raises(ValidationError, match="casilla field override"):
        CasillaFieldOverride.model_validate(
            {
                "selector": {"revision": PREDECESSOR_EDITION, "id": "0001"},
                "fields": fields,
                "removed_fields": (removed,),
            }
        )


def test_a_source_only_change_authors_only_source_refs_and_the_selector(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=casilla(PREDECESSOR_EDITION, "0001", number="1", lineage=None),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=(
            f'casilla_storage_baseline = "{PREDECESSOR_EDITION}"\n'
            f'[[revisions."{SUCCESSOR_EDITION}".casilla_overrides]]\n'
            f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0001" }}\n'
            'fields = { source_refs = ["aeat-form"] }\n'
        ),
        casillas="",
    )

    successor = load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION]

    assert dict(successor.casilla_overrides[0].fields) == {"source_refs": ("aeat-form",)}
    assert successor.casillas[0].number == "1"
    assert successor.casillas[0].source_refs == ("aeat-form",)


def test_storage_reuse_preserves_a_successors_missing_continuity_id(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=casilla(PREDECESSOR_EDITION, "0456", number="456", lineage="annualidades-alimentos"),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=(
            f'casilla_storage_baseline = "{PREDECESSOR_EDITION}"\n'
            f'[[revisions."{SUCCESSOR_EDITION}".casilla_overrides]]\n'
            f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "0456" }}\n'
            'removed_fields = ["continuidad_id"]\n'
        ),
        casillas="",
    )

    definition = load_modelo_directory(modelo_dir)

    assert definition.revisions[PREDECESSOR_EDITION].casillas[0].continuidad_id == "annualidades-alimentos"
    successor = definition.revisions[SUCCESSOR_EDITION].casillas[0]
    assert successor.id == "0456"
    assert successor.continuidad_id is None
    assert successor.continuidad_origin is None
    assert successor.continuidad_evidence is None


def test_an_inherited_row_takes_the_successor_editions_locale_key(tmp_path: Path) -> None:
    """Materialisation runs before enrolment, so no successor row carries a key naming its predecessor."""
    successor = load_modelo_directory(_delta_successor_modelo(tmp_path, declare_predecessor=True)).revisions[
        SUCCESSOR_EDITION
    ]

    inherited = next(casilla for casilla in successor.casillas if casilla.id == "0001")
    assert inherited.localization_keys[0] == casilla_occurrence_locale_key(
        _MODELO_ID, SUCCESSOR_EDITION, "0001", ModeloLocalizationFieldKind.LABEL
    )


def test_a_chain_of_predecessors_resolves_transitively(tmp_path: Path) -> None:
    """A third edition inherits what the second inherited, including the second's overrides."""
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    write_edition(
        modelo_dir,
        _THIRD_EDITION,
        year=_THIRD_EDITION_YEAR,
        manifest_extra=f'predecessor = "{SUCCESSOR_EDITION}"\n',
        casillas=casilla(_THIRD_EDITION, "0001", number="11", lineage="base-imponible"),
    )

    assert _rows(load_modelo_directory(modelo_dir).revisions[_THIRD_EDITION]) == [
        ("0001", "11", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", None),
        ("0005", "5", "recargo-nuevo"),
    ]


def test_every_inherited_row_is_marked_with_the_edition_that_last_stated_it(tmp_path: Path) -> None:
    """The marker follows the edition that stated the row, down the chain, and a stated row carries none."""
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    write_edition(
        modelo_dir,
        _THIRD_EDITION,
        year=_THIRD_EDITION_YEAR,
        manifest_extra=f'predecessor = "{SUCCESSOR_EDITION}"\n',
        casillas=casilla(_THIRD_EDITION, "0001", number="11", lineage="base-imponible"),
    )
    definition = load_modelo_directory(modelo_dir)

    def marks(revision_id: str) -> list[tuple[str, str | None]]:
        return [(casilla.id, casilla.inherited_from) for casilla in definition.revisions[revision_id].casillas]

    assert marks(PREDECESSOR_EDITION) == [("0001", None), ("0002", None), ("0003", None), ("0004", None)]
    assert marks(SUCCESSOR_EDITION) == [
        ("0001", PREDECESSOR_EDITION),
        ("0002", None),
        ("0004", PREDECESSOR_EDITION),
        ("0005", None),
    ]
    assert marks(_THIRD_EDITION) == [
        ("0001", None),
        ("0002", SUCCESSOR_EDITION),
        ("0004", PREDECESSOR_EDITION),
        ("0005", SUCCESSOR_EDITION),
    ]
    # Where a row is stated is not what it means, so the marker never serialises.
    assert all("inherited_from" not in row for row in definition.revisions[_THIRD_EDITION].model_dump()["casillas"])


def test_an_authored_inheritance_marker_is_refused_and_the_repaired_tree_loads(tmp_path: Path) -> None:
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    fragment = modelo_dir / "revisions" / PREDECESSOR_EDITION / "casillas" / "0001-casillas.toml"
    repaired = fragment.read_text(encoding="utf-8")
    fragment.write_text(
        repaired.replace('number = "1"\n', f'number = "1"\ninherited_from = "{_EARLIER_EDITION}"\n', 1),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        RegistryLoadError, match=rf"revision '{PREDECESSOR_EDITION}': casillas \['0001'\] author inherited_from"
    ):
        load_modelo_directory(modelo_dir)

    fragment.write_text(repaired, encoding="utf-8", newline="\n")
    assert (
        load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION].casillas[0].inherited_from == PREDECESSOR_EDITION
    )


_EVIDENCE = "Diseño de registro 2024, campo 1: casilla nueva en el formulario."


def test_an_inherited_row_never_carries_its_predecessors_lineage_claims(tmp_path: Path) -> None:
    """A claim that a box is new on its form is false one edition later, so inheriting drops it.

    The predecessor still carries both claims, so their absence on the
    successor is the merge's doing; a superseding row keeps the claims it
    states itself.
    """
    modelo_dir = modelo_root(tmp_path)
    claims = f'continuidad_origin = "new_on_form"\ncontinuidad_evidence = "{_EVIDENCE}"\n'
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=(
            casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="base-imponible", extra=claims)
            + casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="cuota-integra", extra=claims)
        ),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{PREDECESSOR_EDITION}"\n',
        casillas=casilla(SUCCESSOR_EDITION, "0002", number="22", lineage="cuota-integra", extra=claims),
    )
    definition = load_modelo_directory(modelo_dir)

    def claimed(revision_id: str) -> list[tuple[str, str | None, str | None]]:
        return [
            (casilla.id, casilla.continuidad_origin, casilla.continuidad_evidence)
            for casilla in definition.revisions[revision_id].casillas
        ]

    assert claimed(PREDECESSOR_EDITION) == [("0001", "new_on_form", _EVIDENCE), ("0002", "new_on_form", _EVIDENCE)]
    assert claimed(SUCCESSOR_EDITION) == [("0001", None, None), ("0002", "new_on_form", _EVIDENCE)]


def test_an_edition_declaring_no_predecessor_inherits_nothing(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    _predecessor_edition(modelo_dir)
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=_NO_PREDECESSOR,
        casillas=casilla(SUCCESSOR_EDITION, "0009", number="9", lineage="variante"),
    )

    assert _rows(load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION]) == [("0009", "9", "variante")]


@pytest.mark.parametrize(
    ("stated", "refusal"),
    [
        pytest.param(
            casilla(SUCCESSOR_EDITION, "0001", number="1", lineage="otro-concepto"),
            r"stated casilla '0001' of lineage 'otro-concepto' collides with the inherited casilla '0001' "
            r"of lineage 'base-imponible'",
            id="undeclared-repurpose",
        ),
        pytest.param(
            casilla(SUCCESSOR_EDITION, "0004", number="4", lineage=None),
            r"stated casilla '0004' of lineage \(none declared\) collides with the inherited casilla '0004' "
            r"of lineage \(none declared\)",
            id="collision-without-lineage",
        ),
        pytest.param(
            casilla(SUCCESSOR_EDITION, "0007", number="7", lineage="cuota-integra")
            + casilla(SUCCESSOR_EDITION, "0008", number="8", lineage="cuota-integra"),
            r"states more than one casilla of lineage 'cuota-integra'",
            id="two-stated-rows-one-lineage",
        ),
        pytest.param(
            casilla(SUCCESSOR_EDITION, "0003", number="3", lineage="deduccion-retirada"),
            r"states a casilla of lineage 'deduccion-retirada', which the same edition retires",
            id="stated-and-retired",
        ),
    ],
)
def test_an_ambiguous_override_is_refused_and_the_repaired_tree_loads(
    tmp_path: Path, stated: str, refusal: str
) -> None:
    modelo_dir = _delta_successor_modelo(tmp_path, declare_predecessor=True)
    fragment = modelo_dir / "revisions" / SUCCESSOR_EDITION / "casillas" / "0001-casillas.toml"
    repaired = fragment.read_text(encoding="utf-8")
    fragment.write_text(repaired + stated, encoding="utf-8", newline="\n")

    with pytest.raises(
        RegistryLoadError, match=rf"revision '{SUCCESSOR_EDITION}' inheriting from '{PREDECESSOR_EDITION}': {refusal}"
    ):
        load_modelo_directory(modelo_dir)

    fragment.write_text(repaired, encoding="utf-8", newline="\n")
    assert [casilla.id for casilla in load_modelo_directory(modelo_dir).revisions[SUCCESSOR_EDITION].casillas] == [
        "0001",
        "0002",
        "0004",
        "0005",
    ]


def test_a_predecessor_carrying_one_lineage_twice_cannot_be_superseded(tmp_path: Path) -> None:
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        casillas=(
            casilla(PREDECESSOR_EDITION, "0001", number="1", lineage="repetida")
            + casilla(PREDECESSOR_EDITION, "0002", number="2", lineage="repetida")
        ),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{PREDECESSOR_EDITION}"\n',
        casillas=casilla(SUCCESSOR_EDITION, "0001", number="10", lineage="repetida"),
    )

    with pytest.raises(RegistryLoadError, match=r"carries lineage \['repetida'\] on more than one row"):
        load_modelo_directory(modelo_dir)


def test_a_predecessor_cycle_is_refused_before_anything_is_inherited(tmp_path: Path) -> None:
    """The forest check runs on the raw declarations, so a cycle never reaches the recursion."""
    modelo_dir = modelo_root(tmp_path)
    _predecessor_edition(modelo_dir, manifest_extra=f'predecessor = "{SUCCESSOR_EDITION}"\n')
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{PREDECESSOR_EDITION}"\n',
        casillas=casilla(SUCCESSOR_EDITION, "0005", number="5", lineage="recargo-nuevo"),
    )

    with pytest.raises(RegistryLoadError, match="predecessor declarations form a cycle"):
        load_modelo_directory(modelo_dir)


def test_an_edge_claim_section_is_never_carried_into_the_inheriting_edition(tmp_path: Path) -> None:
    """A continuity evolution belongs to the edge that states it, not to every edition after it.

    ``casilla_continuidad_evolutions`` and ``identifier_evolutions`` record what
    ONE edition did to the identities it received: retired this lineage,
    replaced that binding id. Inheriting them would make the successor
    re-assert a withdrawal it never made, against rows that are already gone --
    and the merge reads retirements from the edition being materialised, so a
    carried-forward row is a live input, not just a stale claim.

    They are excluded by construction: only families in the canonical keyed
    table are merged, and these are not in it. That makes this the test that
    catches one being enrolled by accident, which is the single way the
    exclusion can be lost.

    The inherited casillas are asserted alongside. Without them, an edition
    that inherited nothing at all would satisfy the emptiness above for
    entirely the wrong reason.
    """
    modelo_dir = modelo_root(tmp_path)
    write_edition(
        modelo_dir,
        _EARLIER_EDITION,
        year=_EARLIER_EDITION_YEAR,
        casillas=(
            casilla(_EARLIER_EDITION, "0001", number="1", lineage="base-imponible")
            + casilla(_EARLIER_EDITION, "0002", number="2", lineage="deduccion-retirada")
        ),
    )
    write_edition(
        modelo_dir,
        PREDECESSOR_EDITION,
        year=PREDECESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{_EARLIER_EDITION}"\n',
        casillas="",
        evolutions=retirement(PREDECESSOR_EDITION, lineage="deduccion-retirada", from_revision=_EARLIER_EDITION),
    )
    write_edition(
        modelo_dir,
        SUCCESSOR_EDITION,
        year=SUCCESSOR_EDITION_YEAR,
        manifest_extra=f'predecessor = "{PREDECESSOR_EDITION}"\n',
        casillas="",
    )

    revisions = load_modelo_directory(modelo_dir).revisions
    stating, inheriting = revisions[PREDECESSOR_EDITION], revisions[SUCCESSOR_EDITION]

    assert stating.casilla_continuidad_evolutions != ()
    assert inheriting.casilla_continuidad_evolutions == ()
    assert inheriting.identifier_evolutions == ()
    # The retirement took effect where it was stated and was not re-run after:
    # both editions carry the surviving lineage and neither carries the retired one.
    assert [lineage for _id, _number, lineage in _rows(stating)] == ["base-imponible"]
    assert [lineage for _id, _number, lineage in _rows(inheriting)] == ["base-imponible"]
