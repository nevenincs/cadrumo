"""Predecessor materialisation inherits casillas only; every other family stays authored.

A revision naming a predecessor resolves its casillas from the predecessor
chain, but the completeness manifest, formulas, and export layouts are
declared in full by every edition regardless of a predecessor declaration.
The completeness manifest is the sharpest case: it is casilla-shaped and
authored through the same per-section fragment mechanism as casillas, so a
materialiser written against the raw revision mapping could pick it up by
default -- and its casilla collection is an append array whose
duplicate-identifier validator would then refuse the load with an error
naming a duplicate casilla rather than naming inheritance. These tests drive
the real directory loader over an on-disk TOML tree, with nothing mocked, to
prove the exclusion holds and to show exactly what a materialiser that
merged the manifest anyway would produce.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dev.registry.compiler.loader import load_modelo_directory
from pydantic import ValidationError

from ..errors import RegistryLoadError
from ..schema_surfaces import CalculationCompletenessManifest
from ._loader_directory_mode_support import _write_standard_manifest

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


def test_formulas_and_export_layouts_are_not_inherited_across_a_delta_materialised_edition(tmp_path: Path) -> None:
    """A successor omitting formulas and export layouts has none after materialisation.

    The predecessor declares one of each; the successor states neither.
    Only the casilla family resolves through the predecessor chain, so the
    successor's formulas and export layouts stay exactly what it declared:
    none.
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
        formulas=_formula_toml("2024", formula_id="modelo-999-formula-2024", target_casilla_id="0002"),
        export_layouts=_export_layout_toml("2024", layout_id="modelo-999-layout-2024"),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        manifest_extra='predecessor = "2024"\n',
        casillas=_casilla("2025", "0005", number="5", lineage="recargo-nuevo"),
    )

    definition = load_modelo_directory(modelo_dir)
    predecessor = definition.revisions["2024"]
    successor = definition.revisions["2025"]

    assert len(predecessor.formulas) == 1
    assert len(predecessor.export_layouts) == 1
    assert successor.formulas == ()
    assert successor.export_layouts == ()


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
