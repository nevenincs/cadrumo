"""Tests for workflow concrete adapter boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...domain.deadlines import AutonomoProfile, IVARegime
from . import JsonFileInputsProvider
from ._errors import WorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def test_json_inputs_provider_requires_modelo_period_shape(tmp_path: Path) -> None:
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(
        json.dumps(
            {
                "130": {
                    "2026Q1": {
                        "01": "12500.00",
                        "irpf.previous_year_economic_activity_net_income": "13000",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    values = JsonFileInputsProvider(inputs_path).load_inputs(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
    )

    assert values["01"] == "12500.00"
    assert values["irpf.previous_year_economic_activity_net_income"] == "13000"


def test_json_inputs_provider_rejects_root_casilla_payload(tmp_path: Path) -> None:
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"01": "12500.00"}), encoding="utf-8")

    with pytest.raises(WorkflowError, match="modelo '130'"):
        JsonFileInputsProvider(inputs_path).load_inputs(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
        )
