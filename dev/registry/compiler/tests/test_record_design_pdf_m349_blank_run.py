"""Exact dual-source recovery of the Modelo 349 operator blank tail."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...maintenance_support import resolve_record_design_binary
from .. import record_design_pdf_repairs
from ..loader import load_shared_catalogues
from ..record_design import extract_record_design, extract_record_design_pdf
from ..record_design_pdf_repairs import recover_m349_operator_blank_run
from ..record_design_pdf_rows import parse_pdf_row
from ..record_design_pdf_visual import extract_pdf_text_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _official_pdf() -> tuple[Path, bytes, tuple[str, ...]]:
    root = bundled_path()
    sources = load_shared_catalogues(root / "registry" / "aeat").sources
    resolved = resolve_record_design_binary(
        root,
        sources,
        source_ref="aeat-dr-349-2020-current",
        filing_year=2020,
        design_epoch="2020",
    )
    pdf_bytes = resolved.path.read_bytes()
    return resolved.path, pdf_bytes, extract_pdf_text_lines(pdf_bytes, source_label=str(resolved.path))


def test_operator_tail_is_recovered_from_pinned_pdf_and_boe() -> None:
    path, pdf_bytes, lines = _official_pdf()
    repaired = recover_m349_operator_blank_run(lines, pdf_bytes)
    row = parse_pdf_row(repaired[435], 436)
    assert row is not None
    assert (row.source_row, row.offset, row.length, row.type_code) == (436, 236, 265, "Blancos")

    design = extract_record_design(path).require_complete()
    operator = next(sheet for sheet in design if sheet.name == "Tipo 2 - Registro De Operador Intracomunitario")
    assert operator.total_positions == 500
    assert [(field.row, field.offset, field.length) for field in operator.fields[-2:]] == [
        (433, 196, 40),
        (436, 236, 265),
    ]


def test_operator_tail_refuses_changed_pdf_geometry() -> None:
    _path, pdf_bytes, lines = _official_pdf()
    changed = list(lines)
    changed[435] = "236 499"
    with pytest.raises(RegistryValidationError, match="PDF geometry"):
        recover_m349_operator_blank_run(tuple(changed), pdf_bytes)
    assert recover_m349_operator_blank_run(lines, pdf_bytes + b"changed") == lines


def test_operator_tail_refuses_changed_boe_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, pdf_bytes, lines = _official_pdf()
    assert extract_record_design(path).require_complete()
    renamed = tmp_path / "copied-design.pdf"
    renamed.write_bytes(pdf_bytes)
    assert extract_record_design(renamed).require_complete()
    assert extract_record_design_pdf(renamed).require_complete()
    altered = tmp_path / "boe.html"
    altered.write_text("<td>236-500</td><td>Blancos.</td>", encoding="utf-8")
    monkeypatch.setattr(record_design_pdf_repairs, "resolve_corpus_binary", lambda *_parts: altered)
    with pytest.raises(RegistryValidationError, match="BOE Annex"):
        recover_m349_operator_blank_run(lines, pdf_bytes)
    # The public parser's in-memory and disk caches must not return the earlier
    # 500-byte reading after the corroborating BOE source changes.
    with pytest.raises(RegistryValidationError, match="BOE Annex"):
        extract_record_design(path)
    with pytest.raises(RegistryValidationError, match="BOE Annex"):
        extract_record_design(renamed)
    with pytest.raises(RegistryValidationError, match="BOE Annex"):
        extract_record_design_pdf(renamed)
