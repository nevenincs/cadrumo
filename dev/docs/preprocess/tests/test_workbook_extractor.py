"""Real-behaviour proof of the Diseno de Registro workbook extractor.

Exercises one real official AEAT workbook through the production extractor
(no mocks, no fakes):

* a real ``.xlsx`` and a real ``.xls`` both extract to schema-valid records,
  proving both reader paths (openpyxl and xlrd);
* the casilla-number-to-field-position table content is present in a unit
  (the field number, byte position, length, and the Spanish description);
* the written text sidecar carries a walker-supported extension and the
  installed walker's own filter accepts it (inspected against the real
  installed package, not a copy);
* the rendered sidecar stays under the walker's 10 MB file cap;
* anti-tautology: a tampered provenance sidecar is rejected, and the
  budget-splitter groups units when a render would exceed the cap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...._paths import REPO_ROOT
from .._parts import split_units_by_budget
from .._schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from .._sidecar import (
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sidecar_paths_for,
)
from .._workbook import (
    WORKBOOK_EXTRACTOR_ID,
    _render_sheet,
    build_outputs,
    extract_workbook,
)

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_workbook_extractor.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT
_DISENOS = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "aeat_official" / "disenos_registro"

# A real modern .xlsx Modelo 303 design (openpyxl path) and a real legacy
# .xls Modelo 123 design (xlrd path). Both ship in the corpus.
_XLSX_WORKBOOK = (
    _DISENOS / "modelo_303" / "files" / "01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx"
)
_XLS_WORKBOOK = (
    _DISENOS / "modelo_123" / "files" / "01-123-orden-eha-3435-2007-ejercicio-2024-y-siguientes-190-kb-xls.xls"
)


def test_worked_example_workbooks_exist() -> None:
    """Both real corpus workbooks are present (guards the whole proof)."""
    assert _XLSX_WORKBOOK.is_file(), _XLSX_WORKBOOK
    assert _XLS_WORKBOOK.is_file(), _XLS_WORKBOOK


def test_xlsx_extracts_field_position_table() -> None:
    """The openpyxl path yields a valid record with the field table content.

    Asserts the casilla-number-to-field-position surface a "what is field X"
    query needs: the field number, the byte position, the length, and the
    Spanish description all appear in one sheet's unit.
    """
    outputs = build_outputs(_XLSX_WORKBOOK, repo_root=_REPO_ROOT)

    assert len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, PreprocessOutput)
    assert output.source_kind is SourceDocumentKind.DISENO_REGISTRO_WORKBOOK
    assert output.status is ExtractionStatus.OK
    assert output.preprocessor_id == WORKBOOK_EXTRACTOR_ID
    assert output.source_relpath.endswith(".xlsx")
    # Attribution resolved from the modelo manifest carries the AEAT source
    # and the official download URL.
    assert "AEAT" in output.attribution or "Agencia" in output.attribution
    assert "agenciatributaria.gob.es" in output.attribution

    # The first sheet (DP30300) is the fichero record layout: header row
    # plus numbered field rows with positions, lengths, and descriptions.
    body = "\n".join(unit.text for unit in output.units)
    assert "Posic." in body  # the position column header
    assert "Descripci" in body  # the description column header (accented)
    assert "Modelo" in body  # field 2 description
    assert '"303"' in body  # the constant content for the Modelo field
    # A numbered field row renders number | position | length on one line.
    assert "2 | 3 | 3 | An | Modelo" in body


def test_xls_extracts_via_xlrd() -> None:
    """The legacy .xls path (xlrd) yields a valid, populated record.

    openpyxl cannot open the binary BIFF .xls; this proves the xlrd reader
    path covers the 28 legacy designs and normalises numeric cells (xlrd
    returns floats; field numbers must read as ints).
    """
    outputs = build_outputs(_XLS_WORKBOOK, repo_root=_REPO_ROOT)

    assert len(outputs) == 1
    output = outputs[0]
    assert output.status is ExtractionStatus.OK
    assert output.source_relpath.endswith(".xls")
    body = "\n".join(unit.text for unit in output.units)
    # Field 2 of the Modelo 123 design: the Modelo constant "123". The float
    # field number 2.0 must have normalised to "2", not "2.0".
    assert "2 | 3 | 3 | An | Modelo" in body
    # xlrd returns field numbers/positions as floats; _norm_cell must
    # collapse whole numbers to ints. Verify no cell that is a bare numeric
    # token carries a ".0" tail. (Free prose like a "version 2.0" title cell
    # is not a bare numeric token, so it is correctly excluded.)
    bare_numeric_with_dot_zero = [
        cell
        for line in body.splitlines()
        for cell in line.split(" | ")
        if cell.replace(".", "", 1).isdigit() and cell.endswith(".0")
    ]
    assert not bare_numeric_with_dot_zero


def test_sidecar_round_trips_and_is_walker_indexable(tmp_path: Path) -> None:
    """Written sidecar reloads equal and the .md is accepted by the walker.

    Copies the workbook into tmp so no sidecar lands in the corpus tree
    during the test. Inspects the real installed walker (no mock): the
    rendered .md must pass the extension, size-cap, and binary filters.
    """
    from vaultspec_rag.indexer._chunking import (
        _MAX_FILE_SIZE,
        SUPPORTED_EXTENSIONS,
        _is_binary,
    )

    # Recreate the modelo_303/files/<wb> + sibling manifest so attribution
    # resolution exercises the real manifest read path too.
    files_dir = tmp_path / "modelo_303" / "files"
    files_dir.mkdir(parents=True)
    source_copy = files_dir / _XLSX_WORKBOOK.name
    source_copy.write_bytes(_XLSX_WORKBOOK.read_bytes())
    manifest_src = _XLSX_WORKBOOK.parent.parent / "manifest.json"
    (files_dir.parent / "manifest.json").write_bytes(manifest_src.read_bytes())

    written = extract_workbook(source_copy, repo_root=tmp_path)
    assert len(written) == 1
    text_path = written[0]
    assert text_path.name == source_copy.name + EXTRACTED_TEXT_SUFFIX

    # The provenance sidecar round-trips through the schema unchanged.
    reloaded = load_sidecar(source_copy)
    assert reloaded.source_kind is SourceDocumentKind.DISENO_REGISTRO_WORKBOOK
    assert reloaded.status is ExtractionStatus.OK
    assert reloaded.units  # non-empty

    # The real installed walker would index the rendered .md.
    assert text_path.suffix.lower() in SUPPORTED_EXTENSIONS
    assert text_path.stat().st_size <= _MAX_FILE_SIZE
    assert not _is_binary(text_path)


def test_largest_corpus_sidecar_under_walker_cap() -> None:
    """The biggest workbook's single-part render stays under the 10 MB cap.

    The largest binary workbook (Modelo 200, ~11 MB on disk) renders to a
    small field table; this proves no real corpus workbook needs splitting
    and the indexable sidecar never trips the walker's oversized-file skip.
    """
    from vaultspec_rag.indexer._chunking import _MAX_FILE_SIZE

    biggest = _DISENOS / "modelo_200" / "files" / "01-200-ejercicio-2025-10-9-mb-xls.xls"
    # This is committed corpus; a hard assertion (not a skip) keeps the cap
    # proof from silently passing if the reference workbook ever vanishes.
    assert biggest.is_file(), biggest
    outputs = build_outputs(biggest, repo_root=_REPO_ROOT)
    assert len(outputs) == 1  # no split needed
    rendered_bytes = len(outputs[0].render_text().encode("utf-8"))
    assert rendered_bytes < _MAX_FILE_SIZE


def test_tampered_sidecar_is_rejected(tmp_path: Path) -> None:
    """Anti-tautology: a corrupt provenance sidecar fails to load.

    If this passed with a broken payload the round-trip assertions would be
    vacuous. A truncated sha256 violates the field constraint.
    """
    source_copy = tmp_path / _XLS_WORKBOOK.name
    source_copy.write_bytes(_XLS_WORKBOOK.read_bytes())
    extract_workbook(source_copy, repo_root=tmp_path)

    _, json_path = sidecar_paths_for(source_copy)
    good = json_path.read_text(encoding="utf-8")
    output = load_sidecar(source_copy)
    json_path.write_text(good.replace(output.source_sha256, "deadbeef"), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)


def test_budget_splitter_groups_oversized_units() -> None:
    """The workbook extractor's grouping runs through the canonical splitter.

    Exercises the shared `_parts.split_units_by_budget` splitter directly
    with synthetic oversized units (no real corpus workbook is large enough
    to trigger it), proving that a hypothetical over-cap workbook would
    split rather than ship an oversized, walker-skipped sidecar, and that
    `build_outputs` groups through this exact shared helper rather than a
    private duplicate.
    """
    big = PreprocessUnit(text="x" * (5 * 1024 * 1024))
    groups = split_units_by_budget([big, big, big])
    # Three 5 MB units cannot share an 8 MB budget: expect three groups.
    assert len(groups) == 3
    assert all(len(g) == 1 for g in groups)


def test_workbook_uses_the_canonical_parts_helpers_not_shadow_copies() -> None:
    """Anti-duplication proof: the workbook module imports `_parts` by identity.

    If the workbook extractor still carried a private budget-splitter or
    sidecar-naming re-implementation, its module attribute would be a
    distinct function object rather than the exact `_parts` helper the PDF
    extractor also shares.
    """
    from .. import _parts as parts
    from .. import _workbook as workbook

    assert workbook.split_units_by_budget is parts.split_units_by_budget
    assert workbook.stamp_part_anchors is parts.stamp_part_anchors
    assert workbook.write_part_sidecars is parts.write_part_sidecars


def test_workbook_and_pdf_extractors_share_one_budget_and_naming_scheme() -> None:
    """Workbook and PDF extraction split and name parts through one shared contract.

    Both format extractors delegate multi-part grouping and part naming to
    the same `_parts` helpers, so an oversized workbook and an oversized PDF
    split identically rather than each carrying its own drifted budget or
    naming convention.
    """
    from .. import _pdf as pdf
    from .. import _workbook as workbook
    from .._parts import TEXT_BUDGET_BYTES, part_stand_in_path

    assert pdf.split_units_by_budget is workbook.split_units_by_budget
    assert pdf.stamp_part_anchors is workbook.stamp_part_anchors
    assert pdf.write_part_sidecars is workbook.write_part_sidecars

    source = Path("DR123e24.xlsx")
    assert part_stand_in_path(source, 0, 1) == source
    assert part_stand_in_path(source, 0, 3) == source.with_name("DR123e24.xlsx.part-1")
    assert part_stand_in_path(source, 1, 3) == source.with_name("DR123e24.xlsx.part-2")

    big = PreprocessUnit(text="x" * (5 * 1024 * 1024))
    workbook_groups = workbook.stamp_part_anchors(workbook.split_units_by_budget([big, big, big]))
    pdf_groups = pdf.stamp_part_anchors(pdf.split_units_by_budget([big, big, big]))
    assert len(workbook_groups) == len(pdf_groups) == 3
    assert TEXT_BUDGET_BYTES == 8 * 1024 * 1024


def test_render_sheet_normalises_and_drops_empty_rows() -> None:
    """Row rendering drops fully-empty rows and trims trailing empties.

    Pure-logic check on the renderer: a blank spacer row is dropped, and a
    short row does not render dangling separators for absent trailing cells.
    """
    rendered = _render_sheet(
        "S",
        [
            [1.0, "Posic.", None, None],
            [None, None, None, None],
            ["x", None, None, None],
        ],
    )
    lines = rendered.splitlines()
    assert lines == ["1 | Posic.", "x"]
