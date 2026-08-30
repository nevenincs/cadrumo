"""M303 export applicability has no caller-authored override boundary."""

from __future__ import annotations

import ast
from importlib import import_module
from inspect import signature
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ...modelo._export import ModeloExportCommand
from ...modelo._m303_regimen_simplificado_scope import m303_regimen_simplificado_scope_for_profile
from .. import export_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

modelo_export = import_module("cadrumo.application.modelo._export")
m303_filing_evidence = import_module("cadrumo.application.modelo._m303_filing_evidence")

#: The three Exonerado-390 evidence classes are defined here, not in
#: calculation_revision. That module used to carry them and kept importing
#: them solely to list them in its __all__ long after they moved, so this pin
#: named a module that merely re-exported them.
_CANONICAL_S56_OWNER = "cadrumo/domain/modelos/calculation_revision_m303_evidence.py"
_S56_ACTIVITY_ROW_CLASS = "M303Exonerado390ActivityRowEvidence"
_S56_FILING_EVIDENCE_CLASS = "M303Exonerado390FilingEvidence"
_S56_FILING_EVIDENCE_FIELDS = frozenset(
    {
        "activity_rows",
        "operaciones_terceros_declarables",
        "operaciones_terceros_reference",
    }
)
_RETIRED_M303_EXPORT_OVERRIDE_SURFACE = (
    "m303_applicability",
    "M303ExportApplicabilityEnvelope",
    "M303DifferentiatedSectorValueArrival",
    "M303Exonerado390EndpointValue",
    "M303Exonerado390ValueArrival",
    "M303RegimenSimplificadoValueArrival",
    "project_m303_regimen_simplificado_value_arrival",
    "author_or_replace_filing_instance_evidence",
    "M303RegimenSimplificadoEvidenceRequiredError",
    "explicit applicability envelope",
)


def test_m303_export_applicability_is_internal_to_revision_backed_filing_facts() -> None:
    assert "m303_applicability" not in ModeloExportCommand.model_fields
    assert "m303_applicability" not in signature(export_draft).parameters


def _production_python_sources(source_root: Path) -> tuple[Path, ...]:
    return tuple(
        path for path in scan_directory(source_root, pattern="*.py", recursive=True) if "tests" not in path.parts
    )


def _s56_owner_definitions(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions: set[str] = set()
    for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if class_node.name == _S56_ACTIVITY_ROW_CLASS:
            definitions.add(class_node.name)
        if class_node.name.startswith("M303Exonerado390"):
            for statement in class_node.body:
                if (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id in _S56_FILING_EVIDENCE_FIELDS
                ):
                    definitions.add(f"{class_node.name}.{statement.target.id}")
    return frozenset(definitions)


def test_retired_m303_export_override_has_no_production_surface() -> None:
    source_root = Path(__file__).parents[4]
    production_sources = _production_python_sources(source_root)
    offenders = {
        path.relative_to(source_root).as_posix()
        for path in production_sources
        if any(retired in path.read_text(encoding="utf-8") for retired in _RETIRED_M303_EXPORT_OVERRIDE_SURFACE)
    }
    assert offenders == set()


def test_canonical_profile_scope_mapper_is_required_by_calculation_and_export() -> None:
    """Scope derives from the secured profile, never an export-side input."""
    assert (
        m303_filing_evidence.m303_regimen_simplificado_scope_for_profile is m303_regimen_simplificado_scope_for_profile
    )
    assert modelo_export.m303_regimen_simplificado_scope_for_profile is m303_regimen_simplificado_scope_for_profile


def test_s56_exonerado_390_evidence_owner_is_unique_and_typed() -> None:
    source_root = Path(__file__).parents[4]
    definitions_by_path = {
        path.relative_to(source_root).as_posix(): _s56_owner_definitions(path)
        for path in _production_python_sources(source_root)
        if _s56_owner_definitions(path)
    }
    assert definitions_by_path == {
        _CANONICAL_S56_OWNER: frozenset(
            {
                _S56_ACTIVITY_ROW_CLASS,
                f"{_S56_FILING_EVIDENCE_CLASS}.activity_rows",
                f"{_S56_FILING_EVIDENCE_CLASS}.operaciones_terceros_declarables",
                f"{_S56_FILING_EVIDENCE_CLASS}.operaciones_terceros_reference",
            }
        )
    }

    owner_source = (source_root / _CANONICAL_S56_OWNER).read_text(encoding="utf-8")
    assert "activity_rows: tuple[M303Exonerado390ActivityRowEvidence, ...]" in owner_source
    assert "operaciones_terceros_declarables: bool | None" in owner_source
    assert "operaciones_terceros_reference: FilingEvidenceReference | None" in owner_source
