"""M303 export applicability has no caller-authored override boundary."""

from __future__ import annotations

from inspect import signature
from pathlib import Path

import pytest

from ...modelo import ModeloExportCommand
from .. import export_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_m303_export_applicability_is_internal_to_revision_backed_filing_facts() -> None:
    assert "m303_applicability" not in ModeloExportCommand.model_fields
    assert "m303_applicability" not in signature(export_draft).parameters


def test_retired_m303_export_override_has_no_production_surface() -> None:
    source_root = Path(__file__).parents[4]
    offenders = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*.py")
        if "tests" not in path.parts
        and any(
            retired in path.read_text(encoding="utf-8")
            for retired in (
                "m303_applicability",
                "M303ExportApplicabilityEnvelope",
                "M303FilingFacts",
                "resolve_m303_filing_facts",
                "M303RegimeComposition",
                "m303_regimen_simplificado_scope_for_profile",
                "resolve_m303_regimen_simplificado_scope",
                "M303Exonerado390ActivityRowEvidence",
                "operaciones_terceros_declarables",
                "operaciones_terceros_reference",
                "M303DifferentiatedSectorValueArrival",
                "M303Exonerado390EndpointValue",
                "M303Exonerado390ValueArrival",
                "M303RegimenSimplificadoValueArrival",
                "project_m303_regimen_simplificado_value_arrival",
                "author_or_replace_filing_instance_evidence",
                "M303RegimenSimplificadoEvidenceRequiredError",
                "explicit applicability envelope",
            )
        )
    }
    assert offenders == set()
