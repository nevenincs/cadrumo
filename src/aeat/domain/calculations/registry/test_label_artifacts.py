"""Tests for advisory casilla label-artifact diagnostics."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.resources import bundled_path

from . import load_registry_tree
from ._schema import CasillaDefinition, ModeloDefinition, ModeloRevision, PeriodSelector
from ._validate_label_artifacts import collect_label_artifact_findings

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_CURRENT_UNRESOLVED_PLACEHOLDER_BASELINE = 266
_CURRENT_UNRESOLVED_PLACEHOLDER_TOKENS = frozenset(("{0}", "{2}"))
_SAMPLE_UNRESOLVED_PLACEHOLDER = "{" + "0" + "}"


def _modelo_with_label(label: str) -> ModeloDefinition:
    casilla = CasillaDefinition.model_validate({
        "id": "0001",
        "number": "0001",
        "label": label,
        "section": ("test",),
        "data_type": "money",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    })
    revision = ModeloRevision.model_validate({
        "id": "2025",
        "valid_from": date(2025, 1, 1),
        "period_selector": PeriodSelector(years=(2025,), periods=("0A",)),
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "casillas": (casilla,),
    })
    return ModeloDefinition.model_validate({
        "id": "999",
        "title": "Test modelo",
        "official_name": "Test modelo",
        "tax_domain": "test",
        "cadence": "annual",
        "jurisdiction": "ES-AEAT",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "revisions": {"2025": revision},
    })


def test_label_artifact_inventory_reports_unresolved_format_placeholder() -> None:
    modelo = _modelo_with_label("Importe íntegro {0}([0004]+[0005]-[0006])")

    findings = collect_label_artifact_findings([modelo])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.modelo_id == "999"
    assert finding.revision_id == "2025"
    assert finding.casilla_id == "0001"
    assert finding.artifact == "unresolved_format_placeholder"
    assert finding.placeholder_token == _SAMPLE_UNRESOLVED_PLACEHOLDER


def test_label_artifact_inventory_ignores_normal_casilla_brackets() -> None:
    modelo = _modelo_with_label("Importe íntegro ([0004]+[0005]-[0006])")

    assert collect_label_artifact_findings([modelo]) == ()


def test_committed_corpus_unresolved_placeholder_baseline_does_not_creep() -> None:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))

    findings = collect_label_artifact_findings(modelos)

    assert len(findings) == _CURRENT_UNRESOLVED_PLACEHOLDER_BASELINE
    assert {finding.modelo_id for finding in findings} == {"100"}
    assert {finding.artifact for finding in findings} == {"unresolved_format_placeholder"}
    assert {finding.placeholder_token for finding in findings} == _CURRENT_UNRESOLVED_PLACEHOLDER_TOKENS
