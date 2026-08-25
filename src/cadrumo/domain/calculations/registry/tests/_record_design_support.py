"""Shared support for record-design registry tests."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core.directory_scan import scan_directory
from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.schema import CasillaFieldKind
from cadrumo.domain.calculations.registry.record_design import RecordDesignSheet
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from ..binding_selector_utils import BindingFixedExportSelector, binding_export_selector
from ..record_design import (
    build_diseno_coverage_report,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
    extract_record_design,
    extract_record_design_pdf,
    extract_record_design_pdf_bytes,
)
from ..schema import DataBindingDefinition, ModeloRevision
from ._registry_schema_support import _committed_registry_tree

__all__ = [
    "_MODELO_131_CURRENT",
    "_MODELO_131_WORKBOOK_ROOT",
    "_RECORD_DESIGN_ROOT",
    "CasillaFieldKind",
    "_committed_registry_tree",
    "_fixed_export_selectors",
    "_is_page_one_structured_input_field",
    "_is_structured_input_field",
    "_modelo_131_snapshot",
    "_official_record_design_sheets",
    "_official_record_designs",
    "_page_one_data_type",
    "_record_design_pdf",
    "_record_design_pdf_files",
    "_write_pdf_lines",
    "build_diseno_coverage_report",
    "bundled_path",
    "calculation_closure_record_design_metadata",
    "derive_calculation_completeness_casillas",
    "derive_diseno_coverage_casillas",
    "extract_record_design_pdf",
    "extract_record_design_pdf_bytes",
    "resolve_export_layout",
]

_MODELO_131_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_131", "files")
_MODELO_131_CURRENT = _MODELO_131_WORKBOOK_ROOT / "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"
_RECORD_DESIGN_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")


@cache
def _official_record_design_sheets(path: Path) -> tuple[RecordDesignSheet, ...]:
    return extract_record_design(path).accept_partial()


def _official_record_designs(paths: tuple[Path, ...]) -> dict[Path, tuple[RecordDesignSheet, ...]]:
    # The PDF path is backed by pypdfium2; keep corpus parsing serial to
    # avoid native-library crashes while still deduplicating repeated reads.
    return {path: _official_record_design_sheets(path) for path in paths}


def _modelo_131_snapshot(*, filing_year: int, period: str = "1T"):
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == "131")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period=period)


def _is_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Indicador de fin de registro",
    }:
        return False
    return "RESERVADO" not in description.upper()


def _is_page_one_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Tipo de autoliquidación",
        "Declarante (1) - Nif",
        "Declarante (1) - Apellidos",
        "Declarante (1) - Nombre (solo personas físicas)",
        "Devengo (2) - Ejercicio",
        "Devengo (2) - Período",
        "Indicador de fin de registro",
    }:
        return False
    if "RESERVADO" in description.upper():
        return False
    return "[" not in description and "]" not in description


def _page_one_data_type(offset: int, type_code: str) -> str:
    if offset in {109, 613, 692}:
        return "boolean"
    if offset in {360, 374, 424, 434, 448, 458, 472, 614}:
        return "money"
    if type_code in {"N"}:
        return "money"
    if type_code == "An":
        return "text"
    if offset in {359, 556}:
        return "integer"
    return "decimal"


def _fixed_export_selectors(
    bindings: Iterable[DataBindingDefinition],
    *,
    revision: ModeloRevision,
) -> tuple[tuple[DataBindingDefinition, BindingFixedExportSelector], ...]:
    members: list[tuple[DataBindingDefinition, BindingFixedExportSelector]] = []
    for binding in bindings:
        selector = binding_export_selector(binding, revision=revision)
        if isinstance(selector, BindingFixedExportSelector):
            members.append((binding, selector))
    return tuple(members)


def _record_design_pdf_files() -> tuple[Path, ...]:
    # Recursive, not the fixed-depth "modelo_*/files/*.pdf": Modelo 210 keeps
    # dr210_2011.pdf directly in its modelo directory rather than under
    # files/, and the fixed-depth glob silently dropped it from the corpus
    # this function's callers assert coverage over.
    return scan_directory(_RECORD_DESIGN_ROOT, pattern="*.pdf", recursive=True)


def _record_design_pdf(*path_parts: str) -> Path:
    matches = [path for path in _record_design_pdf_files() if all(part in path.as_posix() for part in path_parts)]
    assert len(matches) == 1, f"expected one record-design PDF for {path_parts!r}, found {matches!r}"
    return matches[0]


def _write_pdf_lines(path: Path, lines: tuple[str, ...]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 8)
    y = A4[1] - 36
    for line in lines:
        if y < 36:
            pdf.showPage()
            pdf.setFont("Helvetica", 8)
            y = A4[1] - 36
        pdf.drawString(36, y, line)
        y -= 12
    pdf.save()
