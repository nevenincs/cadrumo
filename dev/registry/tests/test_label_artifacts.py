"""Tests for advisory casilla label-artifact diagnostics."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.registry_scope import validate_registry_scope
from ..compiler.validate_label_artifacts import (
    collect_label_artifact_findings,
    validate_no_label_artifacts,
)
from ..conformance.registry_schema_support import committed_registry_tree
from .synthetic_locale_fixtures import synthetic_locale_scope, write_test_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SAMPLE_UNRESOLVED_PLACEHOLDER = "{" + "0" + "}"
_TEST_CASILLA_ID: CasillaId = validated_casilla_id("0001", surface="_TEST_CASILLA_ID")
_YEAR = filing_year_envelope().horizon
_REVISION = str(_YEAR)

__all__ = ["synthetic_locale_scope"]


def _modelo_with_label(label: str) -> ModeloDefinition:
    casilla = CasillaDefinition.model_validate(
        {
            "id": _TEST_CASILLA_ID,
            "number": "0001",
            "localization_keys": (write_test_label(label),),
            "section": ("test",),
            "data_type": "money",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        },
    )
    revision = ModeloRevision.model_validate(
        {
            "id": _REVISION,
            "localization_key": f"test.schema.revision.{_REVISION}.label",
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(years=(_YEAR,), periods=("0A",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": (casilla,),
        },
    )
    return ModeloDefinition.model_validate(
        {
            "id": "999",
            "title_localization_key": "test.schema.modelo.999.title",
            "official_name_localization_key": "test.schema.modelo.999.official_name",
            "tax_domain": "iva",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {_REVISION: revision},
        },
    )


def test_label_artifact_inventory_reports_unresolved_format_placeholder() -> None:
    modelo = _modelo_with_label("Importe íntegro {0}([0004]+[0005]-[0006])")

    findings = collect_label_artifact_findings([modelo])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.modelo_id == "999"
    assert finding.revision_id == _REVISION
    assert finding.casilla_id == _TEST_CASILLA_ID
    assert finding.artifact == "unresolved_format_placeholder"
    assert finding.placeholder_token == _SAMPLE_UNRESOLVED_PLACEHOLDER


def test_label_artifact_validator_reports_unresolved_format_placeholder() -> None:
    modelo = _modelo_with_label("Importe íntegro {0}([0004]+[0005]-[0006])")

    failures = validate_no_label_artifacts([modelo])

    assert len(failures) == 1
    assert f"modelo 999 revision {_REVISION} casilla 0001" in failures[0]
    assert "unresolved_format_placeholder" in failures[0]


def test_label_artifact_inventory_ignores_normal_casilla_brackets() -> None:
    modelo = _modelo_with_label("Importe íntegro ([0004]+[0005]-[0006])")

    assert collect_label_artifact_findings([modelo]) == ()


def test_committed_corpus_has_no_unresolved_label_placeholders() -> None:
    modelos, _ = committed_registry_tree()

    findings = collect_label_artifact_findings(modelos)

    assert findings == ()


def test_registry_scope_rejects_unresolved_label_placeholder() -> None:
    modelo = _modelo_with_label("Importe íntegro {0}([0004]+[0005]-[0006])")

    failures = validate_registry_scope([modelo])

    assert any("unresolved_format_placeholder" in failure for failure in failures)
