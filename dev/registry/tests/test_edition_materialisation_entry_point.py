"""The public entry point that resolves one edition into its full-copy raw revision table."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.toml import render_toml
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.edition_materialisation import materialise_edition, resolve_edition
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_grammar import REVISION_SECTION_FIELDS
from ..conformance.edition import ReviewCoverage, read_registry_edition
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_chain_materialisation import chain_materialisation
from ..edition_delta_source import read_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_THIRD_YEAR = filing_year_envelope().horizon
_SECOND_YEAR = _THIRD_YEAR - 1
_FIRST_YEAR = _SECOND_YEAR - 1
_FIRST, _SECOND, _THIRD = str(_FIRST_YEAR), str(_SECOND_YEAR), str(_THIRD_YEAR)
_ABSENT = str(_THIRD_YEAR + 1)
_REVIEWED_AT = date(_THIRD_YEAR, 9, 10)

_LEGAL_REF = "ley-58-2003:art-29"


def _write_edition(
    modelo_dir: Path, revision_id: str, *, year: int, rows: tuple[tuple[str, str], ...], extra: str
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f"{extra}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        "".join(
            f'[[revisions."{revision_id}".casillas]]\nid = "{casilla_id}"\nnumber = "{casilla_id}"\n'
            f'section = ["liquidacion"]\ncontinuidad_id = "{lineage}"\n'
            f'legal_refs = ["{_LEGAL_REF}"]\nsource_refs = ["aeat-manual"]\n\n'
            for casilla_id, lineage in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def _modelo(tmp_path: Path, *, successor_extra: str) -> Path:
    modelo_dir = tmp_path / "999"
    modelo_dir.mkdir()
    write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, _SECOND, year=_SECOND_YEAR, rows=(("1", "base"), ("2", "cuota")), extra="")
    _write_edition(modelo_dir, _THIRD, year=_THIRD_YEAR, rows=(("3", "recargo"),), extra=successor_extra)
    return modelo_dir


def test_a_delta_edition_resolves_to_every_row_and_names_no_predecessor(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra=f'predecessor = "{_SECOND}"\n'), _THIRD)

    assert edition.inherits_from == _SECOND
    assert "predecessor" not in edition.table
    rows = edition.table["casillas"]
    assert isinstance(rows, tuple)
    assert [row["continuidad_id"] for row in rows] == ["base", "cuota", "recargo"]
    assert edition.label_origins == (_SECOND, _SECOND, None)


def test_an_edition_stating_every_row_is_returned_as_declared(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra=""), _THIRD)

    assert edition.inherits_from is None
    assert edition.label_origins is None
    rows = edition.table["casillas"]
    assert isinstance(rows, tuple)
    assert [row["continuidad_id"] for row in rows] == ["recargo"]


def test_an_edition_the_modelo_does_not_declare_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match=f"no edition '{_ABSENT}'"):
        materialise_edition(_modelo(tmp_path, successor_extra=""), _ABSENT)


def test_a_named_predecessor_absent_from_the_tree_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match=_FIRST):
        materialise_edition(_modelo(tmp_path, successor_extra=f'predecessor = "{_FIRST}"\n'), _THIRD)


_REVIEWED_DELTA = (
    f'predecessor = "{_SECOND}"\n'
    'engineered_by = "agent:author"\n'
    'review_status = "agent_reviewed"\n'
    'reviewed_by = "agent:reviewer"\n'
    f"reviewed_at = {_REVIEWED_AT.isoformat()}\n"
    f'reviewed_against = "{_SECOND}"\n'
)


def _standalone(table: object) -> ModeloRevision:
    """Validate a materialised table's revision scalars as the edition's only source, with no predecessor present.

    The casilla rows are left out because their locale keys are computed by the
    loader, and the stamp rules read nothing from them.
    """
    assert isinstance(table, dict)
    scalars = {key: value for key, value in table.items() if key != "casillas"}
    return ModeloRevision.model_validate({**scalars, "id": _THIRD, "localization_key": "standalone"})


def test_a_reviewed_delta_edition_preserves_its_review_when_materialised(
    tmp_path: Path,
) -> None:
    """Removing inheritance changes representation, not the historical comparison review."""
    edition = materialise_edition(_modelo(tmp_path, successor_extra=_REVIEWED_DELTA), _THIRD)

    assert edition.table["review_status"] == "agent_reviewed"
    assert edition.table["reviewed_by"] == "agent:reviewer"
    reviewed_at = edition.table["reviewed_at"]
    assert isinstance(reviewed_at, date)
    assert reviewed_at == _REVIEWED_AT
    assert edition.table["reviewed_against"] == _SECOND
    assert edition.table["engineered_by"] == "agent:author"
    standalone = _standalone(edition.table)
    assert standalone.review_status.value == "agent_reviewed"
    assert standalone.reviewed_against == _SECOND


def test_materialisation_does_not_rewrite_the_historical_comparison(tmp_path: Path) -> None:
    modelos = tmp_path / "modelos"
    modelos.mkdir()
    modelo = _modelo(modelos, successor_extra=_REVIEWED_DELTA)
    edition = materialise_edition(modelo, _THIRD)

    assert _standalone(edition.table).reviewed_against == _SECOND
    scope = read_registry_edition("999", _THIRD, registry_root=tmp_path).review_scope
    assert scope.coverage is ReviewCoverage.STATED_ROWS
    assert scope.reviewed_against == _SECOND
    assert scope.rendered_review_status == "agent_reviewed"


def test_a_dangling_review_comparison_is_refused_specifically(tmp_path: Path) -> None:
    invalid = _REVIEWED_DELTA.replace(f'reviewed_against = "{_SECOND}"', f'reviewed_against = "{_FIRST}"')

    with pytest.raises(RegistryLoadError, match=rf"dangling review reference reviewed_against='{_FIRST}'"):
        load_modelo_directory(_modelo(tmp_path, successor_extra=invalid))


def test_storage_inheritance_does_not_import_the_baseline_review(tmp_path: Path) -> None:
    modelo = _modelo(tmp_path, successor_extra=f'predecessor = "{_SECOND}"\n')
    predecessor_manifest = modelo / "revisions" / _SECOND / "revision.toml"
    predecessor_manifest.write_text(
        predecessor_manifest.read_text(encoding="utf-8")
        + f'review_status = "agent_reviewed"\nreviewed_by = "agent:source"\nreviewed_at = {_REVIEWED_AT.isoformat()}\n',
        encoding="utf-8",
        newline="\n",
    )

    definition = load_modelo_directory(modelo)

    assert definition.revisions[_SECOND].review_status.value == "agent_reviewed"
    assert definition.revisions[_THIRD].review_status.value == "pending_review"
    assert definition.revisions[_THIRD].reviewed_by is None


def test_an_edition_stating_every_row_keeps_its_review(tmp_path: Path) -> None:
    extra = (
        f'review_status = "agent_reviewed"\nreviewed_by = "agent:reviewer"\nreviewed_at = {_REVIEWED_AT.isoformat()}\n'
    )
    edition = materialise_edition(_modelo(tmp_path, successor_extra=extra), _THIRD)

    assert edition.table["review_status"] == "agent_reviewed"
    assert edition.table["reviewed_by"] == "agent:reviewer"


def test_an_unreviewed_delta_edition_withdraws_nothing(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra=f'predecessor = "{_SECOND}"\n'), _THIRD)

    assert edition.table.get("review_status", "pending_review") == "pending_review"


def _attested_modelo(tmp_path: Path, *, extra: str = "") -> Path:
    return _modelo(
        tmp_path,
        successor_extra=f'predecessor = "{_SECOND}"\n'
        f'[[revisions."{_THIRD}".lineage_attestations]]\n'
        'family = "casillas"\ncontinuidad_id = "base"\n'
        f'from_revision = "{_SECOND}"\nto_revision = "{_THIRD}"\norigin = "grounded"\n'
        'evidence = "The same officially identified base is carried on this edge."\n'
        f'legal_refs = ["{_LEGAL_REF}"]\nsource_refs = ["aeat-manual"]\n{extra}',
    )


def test_materialised_sidecar_is_an_exact_inline_claim_on_a_standalone_edition(tmp_path: Path) -> None:
    modelo = _attested_modelo(tmp_path)
    before = load_modelo_directory(modelo).revisions[_THIRD]
    edition = materialise_edition(modelo, _THIRD)
    assert "lineage_attestations" not in edition.table
    standalone = tmp_path / "standalone"
    standalone.mkdir()
    write_standard_manifest(standalone, "Detached attestation")
    revision_dir = standalone / "revisions" / _THIRD
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        render_toml(
            {
                "revisions": {
                    _THIRD: {key: value for key, value in edition.table.items() if key not in REVISION_SECTION_FIELDS}
                }
            }
        ),
        encoding="utf-8",
    )
    (revision_dir / "casillas" / "0001-declarations.toml").write_text(
        render_toml({"revisions": {_THIRD: {"casillas": edition.table["casillas"]}}}), encoding="utf-8"
    )
    after = load_modelo_directory(standalone).revisions[_THIRD]
    original = next(row for row in before.casillas if row.continuidad_id == "base")
    detached = next(row for row in after.casillas if row.continuidad_id == "base")
    for field in ("continuidad_origin", "continuidad_evidence", "legal_refs", "source_refs"):
        assert getattr(detached, field) == getattr(original, field)
    assert detached.continuidad_origin is not None


@pytest.mark.parametrize("field", ["legal_refs", "source_refs"])
def test_materialisation_does_not_discard_distinct_sidecar_references(tmp_path: Path, field: str) -> None:
    modelo = _attested_modelo(tmp_path)
    manifest = modelo / "revisions" / _THIRD / "revision.toml"
    text = manifest.read_text("utf-8")
    original = f'legal_refs = ["{_LEGAL_REF}"]' if field == "legal_refs" else 'source_refs = ["aeat-manual"]'
    replacement = 'legal_refs = ["ley-58-2003:art-30"]' if field == "legal_refs" else 'source_refs = ["other-source"]'
    head, separator, tail = text.partition(f'[[revisions."{_THIRD}".lineage_attestations]]')
    manifest.write_text(head + separator + tail.replace(original, replacement), encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="without losing its distinct legal_refs or source_refs"):
        materialise_edition(modelo, _THIRD)

    resolved = resolve_edition(modelo, _THIRD)
    assert resolved.table["predecessor"] == _SECOND
    before = load_modelo_directory(modelo).revisions[_THIRD]
    source = read_edition(modelo, _THIRD)
    assert source.table["lineage_attestations"] == resolved.table["lineage_attestations"]
    row = next(row for row in source.rows if row["continuidad_id"] == "base")
    assert row[field] == list(getattr(before.casillas[0], field))
    assert row["continuidad_origin"] == "grounded"
    # Distinct edge evidence must remain part of the normalization proof;
    # changing only it cannot compare equal to the original edition.
    proof = chain_materialisation(source)
    assert (b"other-source" if field == "source_refs" else b"ley-58-2003:art-30") in proof
    manifest.write_text(head + separator + tail, encoding="utf-8")
    assert chain_materialisation(read_edition(modelo, _THIRD)) != proof


def test_materialisation_validates_sidecar_edge_before_projecting_its_claim(tmp_path: Path) -> None:
    modelo = _attested_modelo(tmp_path)
    manifest = modelo / "revisions" / _THIRD / "revision.toml"
    manifest.write_text(
        manifest.read_text("utf-8").replace(f'from_revision = "{_SECOND}"', f'from_revision = "{_FIRST}"'),
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="canonical predecessor"):
        materialise_edition(modelo, _THIRD)


def test_materialisation_refuses_an_attestation_with_no_inline_family_representation(tmp_path: Path) -> None:
    modelo = _attested_modelo(tmp_path)
    manifest = modelo / "revisions" / _THIRD / "revision.toml"
    manifest.write_text(
        manifest.read_text("utf-8").replace(
            'family = "casillas"\ncontinuidad_id = "base"', 'family = "formulas"\nmember = "base-formula"'
        ),
        encoding="utf-8",
    )
    directory = modelo / "revisions" / _SECOND / "formulas"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(
        f'[[revisions."{_SECOND}".formulas]]\nid = "base-formula"\ntarget_casilla_id = "1"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\nsource_refs = ["aeat-manual"]\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="no inline lineage claim representation"):
        materialise_edition(modelo, _THIRD)
