"""Predecessor materialisation carries keyed families and refuses silence on scoped ones.

An edition naming a predecessor resolves its casillas through the continuity
merge and every other KEYED family through the identity union: a formula the
edition does not restate is the predecessor's formula, which is what makes a
delta edition able to state only its differences.

A SCOPED family is the exception, and is scoped precisely because carrying it
silently would be a claim nobody made: the completeness manifest and the
export layouts describe the edition's OWN surface, so an edition that states
none of them must say whether it means the predecessor's (``scoped_families``)
or none at all (``cleared_families``). Silence is refused rather than resolved.

The completeness manifest is the sharpest case: it is casilla-shaped and
authored through the same per-section fragment mechanism as casillas, so a
materialiser written against the raw revision mapping could pick it up by
default -- and its casilla collection is an append array whose
duplicate-identifier validator would then refuse the load with an error
naming a duplicate casilla rather than naming inheritance. These tests drive
the real directory loader over an on-disk TOML tree, with nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema_surfaces import CalculationCompletenessManifest

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "999"
_LEGAL_REF = "ley-58-2003:art-29"
_SOURCE_REF = "aeat-manual"


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str | None) -> str:
    lineage_line = f'continuidad_id = "{lineage}"\n' if lineage is not None else ""
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f"{lineage_line}"
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _completeness_manifest_toml(revision_id: str, *, casilla_rows: tuple[tuple[str, str], ...]) -> str:
    """Build one ``completeness_manifest`` fragment naming the given ``(casilla_id, number)`` rows."""
    rows = "".join(
        f'[[revisions."{revision_id}".completeness_manifest.casillas]]\n'
        f'casilla_id = "{casilla_id}"\n'
        f'number = "{number}"\n\n'
        for casilla_id, number in casilla_rows
    )
    return (
        f'[revisions."{revision_id}".completeness_manifest]\n'
        f'source_ref = "{_SOURCE_REF}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        f"{rows}"
    )


def _formula_toml(revision_id: str, *, formula_id: str, target_casilla_id: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target_casilla_id}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
    )


def _export_layout_toml(revision_id: str, *, layout_id: str) -> str:
    return (
        f'[[revisions."{revision_id}".export_layouts]]\n'
        f'id = "{layout_id}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    manifest_extra: str = "",
    completeness_manifest: str = "",
    formulas: str = "",
    export_layouts: str = "",
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
            f'source_refs = ["{_SOURCE_REF}"]\n'
            f"{manifest_extra}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas").mkdir()
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    if completeness_manifest:
        (revision_dir / "completeness_manifest").mkdir()
        (revision_dir / "completeness_manifest" / "0001-completeness-manifest.toml").write_text(
            completeness_manifest, encoding="utf-8", newline="\n"
        )
    if formulas:
        (revision_dir / "formulas").mkdir()
        (revision_dir / "formulas" / "0001-formulas.toml").write_text(formulas, encoding="utf-8", newline="\n")
    if export_layouts:
        (revision_dir / "export_layouts").mkdir()
        (revision_dir / "export_layouts" / "0001-export-layouts.toml").write_text(
            export_layouts, encoding="utf-8", newline="\n"
        )


def _modelo_root(root: Path) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def test_a_successor_manifest_is_not_inherited_from_a_predecessor_with_manifest_rows(tmp_path: Path) -> None:
    """A materialised successor's manifest is exactly what it authored, never the predecessor's rows.

    The predecessor's manifest and the successor's own manifest share the
    casilla id ``0002``. If materialisation inherited the completeness
    manifest and merged it the way it merges casillas, that shared id would
    appear twice and the duplicate-identifier validator would refuse the
    load naming a collision rather than naming inheritance. The load
    succeeding at all is therefore already part of the proof; the equality
    check below confirms the surviving manifest is the successor's own.
    """
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=(
            _casilla("2024", "0001", number="1", lineage="base-imponible")
            + _casilla("2024", "0002", number="2", lineage="cuota-integra")
        ),
        completeness_manifest=_completeness_manifest_toml("2024", casilla_rows=(("0001", "1"), ("0002", "2"))),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
        completeness_manifest=_completeness_manifest_toml("2025", casilla_rows=(("0002", "2"),)),
    )

    successor = load_modelo_directory(modelo_dir).revisions["2025"]

    expected_manifest = CalculationCompletenessManifest.model_validate(
        {
            "source_ref": _SOURCE_REF,
            "casillas": ({"casilla_id": "0002", "number": "2"},),
            "legal_refs": (_LEGAL_REF,),
            "source_refs": (_SOURCE_REF,),
        }
    )
    assert successor.completeness_manifest == expected_manifest
    assert {casilla.casilla_id for casilla in successor.completeness_manifest.casillas} == {"0002"}


def _predecessor_with_formula_and_layout(modelo_dir: Path) -> None:
    """Author the 2024 edition every case below inherits from."""
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=(
            _casilla("2024", "0001", number="1", lineage="base-imponible")
            + _casilla("2024", "0002", number="2", lineage="cuota-integra")
        ),
        formulas=_formula_toml("2024", formula_id="modelo-999-formula-2024", target_casilla_id="0002"),
        export_layouts=_export_layout_toml("2024", layout_id="modelo-999-layout-2024"),
    )


def test_a_keyed_family_the_successor_does_not_restate_is_carried_from_its_predecessor(tmp_path: Path) -> None:
    """A formula the successor omits resolves to the predecessor's, by identity union.

    This is what lets a delta edition state only its differences: omission
    inherits. The successor here states no formulas at all and still carries
    the predecessor's, and it declines the scoped export layouts explicitly so
    that this case is about the KEYED family alone.
    """
    modelo_dir = _modelo_root(tmp_path)
    _predecessor_with_formula_and_layout(modelo_dir)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\ncleared_families = ["export_layouts"]\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    definition = load_modelo_directory(modelo_dir)
    predecessor = definition.revisions["2024"]
    successor = definition.revisions["2025"]

    assert {formula.id for formula in predecessor.formulas} == {"modelo-999-formula-2024"}
    assert {formula.id for formula in successor.formulas} == {"modelo-999-formula-2024"}
    assert successor.export_layouts == ()


def test_a_scoped_family_the_successor_leaves_undecided_is_refused(tmp_path: Path) -> None:
    """Detector teeth: silence about the predecessor's export layouts fails closed.

    The export layout describes the edition's own filing surface, so carrying
    it over unasked would assert a design the successor never reviewed and
    dropping it would withdraw one just as quietly. The loader refuses instead,
    naming the family and both words that decide it.
    """
    modelo_dir = _modelo_root(tmp_path)
    _predecessor_with_formula_and_layout(modelo_dir)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    with pytest.raises(RegistryLoadError, match=r"neither asserts 'export_layouts' in scoped_families"):
        load_modelo_directory(modelo_dir)


def test_asserting_a_scoped_family_carries_it_and_declining_it_takes_none(tmp_path: Path) -> None:
    """The two explicit answers resolve to the two different outcomes silence could not choose between."""
    asserted_dir = _modelo_root(tmp_path / "asserted")
    _predecessor_with_formula_and_layout(asserted_dir)
    _write_edition(
        asserted_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\nscoped_families = ["export_layouts"]\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    declined_dir = _modelo_root(tmp_path / "declined")
    _predecessor_with_formula_and_layout(declined_dir)
    _write_edition(
        declined_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\ncleared_families = ["export_layouts"]\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    asserted = load_modelo_directory(asserted_dir).revisions["2025"]
    declined = load_modelo_directory(declined_dir).revisions["2025"]

    assert {layout.id for layout in asserted.export_layouts} == {"modelo-999-layout-2024"}
    assert declined.export_layouts == ()


def test_a_hand_merged_manifest_shape_is_refused_by_the_duplicate_casilla_id_check(tmp_path: Path) -> None:
    """Detector teeth: the refusal a manifest-merging materialiser would produce, without touching it.

    ``_inherit_casillas`` in the loader internals owns the casilla merge and
    is not touched here; it belongs to a different step. This test instead
    authors, as a plain revision, the exact shape a materialiser would
    produce if it merged the completeness manifest the way it merges
    casillas: the predecessor's rows followed by the successor's own row for
    a lineage both sides cover. Loading that shape through the real
    directory loader hits the same typed validator the materialised
    successor above never reaches, and the refusal names the same casilla
    id ``0002`` that stayed singular in the test above.
    """
    modelo_dir = _modelo_root(tmp_path)
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
        completeness_manifest=_completeness_manifest_toml(
            "2025",
            casilla_rows=(("0001", "1"), ("0002", "2"), ("0002", "2")),
        ),
    )

    with pytest.raises(RegistryLoadError, match=r"declares duplicate casilla ids: '0002'"):
        load_modelo_directory(modelo_dir)

    # The same typed validator, exercised directly: a merging materialiser's
    # output would fail model construction with this exact message even
    # outside the loader, which is the failure this suite would see if the
    # exclusion in `_materialise_revision` were ever weakened to also carry
    # the manifest.
    with pytest.raises(ValidationError, match=r"declares duplicate casilla ids: '0002'"):
        CalculationCompletenessManifest.model_validate(
            {
                "source_ref": _SOURCE_REF,
                "casillas": (
                    {"casilla_id": "0001", "number": "1"},
                    {"casilla_id": "0002", "number": "2"},
                    {"casilla_id": "0002", "number": "2"},
                ),
                "legal_refs": (_LEGAL_REF,),
                "source_refs": (_SOURCE_REF,),
            }
        )
