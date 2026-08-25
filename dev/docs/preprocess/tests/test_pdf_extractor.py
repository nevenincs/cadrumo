"""Real-behaviour proof of the corpus PDF text extractor.

Exercises one real corpus PDF through the production extractor (no mocks):

* a real Diseno-de-registro instruction PDF extracts to a schema-valid
  record with readable per-page text;
* attribution resolves from the real manifest (both shipped manifest shapes
  are covered: the per-artefact diseno manifest and the flat manuales one);
* the written text sidecar carries a walker-supported extension and the
  installed walker's own filter accepts it (real installed package, no mock);
* the budget splitter keeps every emitted part under the 10 MB walker cap;
* anti-tautology: a tampered provenance sidecar is rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...._paths import REPO_ROOT
from .._parts import TEXT_BUDGET_BYTES, split_units_by_budget, stamp_part_anchors
from .._pdf import (
    PDF_EXTRACTOR_ID,
    _attribution_for,
    build_outputs,
    extract_pdf,
)
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

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_pdf_extractor.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT
_CORPUS = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"

# A small real Diseno-de-registro instruction PDF (26 KB, one page) - fast to
# extract and grounded by a per-artefact manifest. The manuales PDFs are
# hundreds of pages and minutes to extract; the small PDF proves the contract.
_SMALL_PDF = (
    _CORPUS
    / "aeat_official"
    / "disenos_registro"
    / "modelo_131"
    / "files"
    / "08-131-orden-eha-580-2009-ejercicios-2009-a-2014-26-kb-pdf.pdf"
)
# A real manuales PDF (flat source_pdf_url manifest) - used only for the
# attribution-shape assertion, not extracted (it is large).
_MANUAL_PDF = _CORPUS / "manuals" / "renta" / "2025" / "part1" / "source.pdf"


def test_worked_example_pdf_exists() -> None:
    """The small real corpus PDF is present (guards the whole proof)."""
    assert _SMALL_PDF.is_file(), _SMALL_PDF


def test_pdf_extracts_readable_per_page_text() -> None:
    """The extractor yields a valid record with readable per-page units.

    Asserts the BOE/AEAT definition surface a query needs: real Spanish text
    is present, one unit per non-empty page, titled by page number.
    """
    outputs = build_outputs(_SMALL_PDF, repo_root=_REPO_ROOT)

    assert len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, PreprocessOutput)
    assert output.source_kind is SourceDocumentKind.CORPUS_PDF
    assert output.status is ExtractionStatus.OK
    assert output.preprocessor_id == PDF_EXTRACTOR_ID
    assert output.source_relpath.endswith(".pdf")
    assert output.units
    first = output.units[0]
    assert first.title == "Pag. 1"
    # Readable Spanish content from the Modelo 131 design instruction PDF.
    assert "Modelo 131" in first.text
    assert "Agencia Tributaria" in first.text


def test_attribution_resolves_for_both_manifest_shapes() -> None:
    """Diseno (per-artefact) and manuales (flat) manifests both attribute.

    Both must carry the AEAT source and pin the official download URL so no
    corpus text ships unattributed.
    """
    diseno = _attribution_for(_SMALL_PDF)
    assert "AEAT" in diseno
    assert "agenciatributaria.gob.es" in diseno

    if _MANUAL_PDF.is_file():
        manual = _attribution_for(_MANUAL_PDF)
        assert "agenciatributaria.gob.es" in manual
        assert "Manual" in manual  # the manuales URL path


def test_sidecar_round_trips_and_is_walker_indexable(tmp_path: Path) -> None:
    """Written sidecar reloads equal and the .md is accepted by the walker.

    Copies the PDF and its manifest into tmp so no sidecar lands in the
    corpus tree. Inspects the real installed walker (no mock): the rendered
    .md must pass the extension, size-cap, and binary filters.
    """
    from vaultspec_rag.indexer._chunking import (
        _MAX_FILE_SIZE,
        SUPPORTED_EXTENSIONS,
        _is_binary,
    )

    # Recreate modelo_131/{manifest.json, files/<pdf>} so the diseno
    # attribution read path is exercised against a real manifest.
    files_dir = tmp_path / "modelo_131" / "files"
    files_dir.mkdir(parents=True)
    source_copy = files_dir / _SMALL_PDF.name
    source_copy.write_bytes(_SMALL_PDF.read_bytes())
    manifest_src = _SMALL_PDF.parent.parent / "manifest.json"
    (files_dir.parent / "manifest.json").write_bytes(manifest_src.read_bytes())

    written = extract_pdf(source_copy, repo_root=tmp_path)
    assert len(written) == 1
    text_path = written[0]
    assert text_path.name == source_copy.name + EXTRACTED_TEXT_SUFFIX

    reloaded = load_sidecar(source_copy)
    assert reloaded.source_kind is SourceDocumentKind.CORPUS_PDF
    assert reloaded.status is ExtractionStatus.OK
    assert reloaded.units

    assert text_path.suffix.lower() in SUPPORTED_EXTENSIONS
    assert text_path.stat().st_size <= _MAX_FILE_SIZE
    assert not _is_binary(text_path)


def test_tampered_sidecar_is_rejected(tmp_path: Path) -> None:
    """Anti-tautology: a corrupt provenance sidecar fails to load.

    If this passed with a broken payload the round-trip assertions would be
    vacuous. A truncated sha256 violates the field constraint.
    """
    source_copy = tmp_path / _SMALL_PDF.name
    source_copy.write_bytes(_SMALL_PDF.read_bytes())
    extract_pdf(source_copy, repo_root=tmp_path)

    _, json_path = sidecar_paths_for(source_copy)
    good = json_path.read_text(encoding="utf-8")
    output = load_sidecar(source_copy)
    json_path.write_text(good.replace(output.source_sha256, "deadbeef"), "utf-8")
    with pytest.raises(PreprocessSidecarError):
        load_sidecar(source_copy)


def test_budget_splitter_keeps_parts_under_cap() -> None:
    """The splitter groups oversized units so each part stays under the cap.

    No real corpus PDF extracts to more than the 8 MB budget (even a 1466-page
    manual renders to ~3 MB), so the splitter is proven directly with
    synthetic oversized units, anchor-stamped as multi-part.
    """
    from vaultspec_rag.indexer._chunking import _MAX_FILE_SIZE

    big = PreprocessUnit(text="x" * (5 * 1024 * 1024))
    groups = stamp_part_anchors(split_units_by_budget([big, big, big]))
    assert len(groups) == 3
    for index, group in enumerate(groups):
        # Each part is anchor-stamped and renders under the hard walker cap.
        assert all(unit.anchor == f"part-{index + 1}" for unit in group)
        rendered_bytes = sum(len(u.text.encode("utf-8")) for u in group)
        assert rendered_bytes < _MAX_FILE_SIZE
    # The budget is a margin below the hard cap.
    assert TEXT_BUDGET_BYTES < _MAX_FILE_SIZE


def test_unsupported_extension_is_refused(tmp_path: Path) -> None:
    """A non-PDF handed to the PDF extractor fails loudly, never silently."""
    non_pdf_path = tmp_path / "not-a-pdf.txt"
    non_pdf_path.write_text("x", encoding="utf-8")
    with pytest.raises(PreprocessSidecarError):
        build_outputs(non_pdf_path, repo_root=tmp_path)
