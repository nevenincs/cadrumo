"""Google CLI payload schema guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import CasillaId, validated_casilla_id
from .._config._google_payloads import (
    GoogleSyncCalcComputeResult,
    GoogleSyncCalcPullResult,
    GoogleSyncCalcVerifyResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_INGRESOS_CASILLA")
_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_RENDIMIENTO_NETO_CASILLA")
_EMPTY_CASILLA_ID = ""
_LEGAL_REF = "orden-hac-test:art-1"
_SOURCE_REF = "aeat-modelo-130-test-source"


def _casilla_id_from_payload(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


def _base_pull_payload() -> dict[str, object]:
    return {
        "profile": "default",
        "modelo": "130",
        "revision": "2019-y-siguientes",
        "period": "1T",
        "year": 2025,
        "spreadsheet_id": "spreadsheet-id",
        "metadata_match": "matches",
        "metadata": {},
        "cells_read": 2,
        "operator_edits_total": 1,
        "operator_edits_populated": 1,
        "binding_edits_populated": 0,
        "relation_edits_populated": 0,
        "operator_edits": [{"casilla_id": _INGRESOS_CASILLA, "label": "Ingresos", "value": "100.00"}],
        "binding_edits": [],
        "relation_edits": [],
        "row_set_edits_populated": 0,
        "row_set_cells_populated": 0,
        "assembled_groupings": [],
        "assembled_observation_count": 0,
        "row_set_edits": [],
    }


def _base_compute_payload() -> dict[str, object]:
    return {
        "profile": "default",
        "modelo": "130",
        "revision": "2019-y-siguientes",
        "period": "1T",
        "year": 2025,
        "spreadsheet_id": "spreadsheet-id",
        "metadata_match": "matches",
        "cells_read": 2,
        "operator_edits_populated": 1,
        "binding_edits_populated": 0,
        "relation_edits_populated": 0,
        "computed": [
            {
                "casilla_id": _RENDIMIENTO_NETO_CASILLA,
                "value": "20.00",
                "formula_id": "m130-test-formula",
                "legal_refs": [_LEGAL_REF],
                "source_refs": [_SOURCE_REF],
            },
        ],
    }


def test_google_calc_pull_payload_types_casilla_rows() -> None:
    payload = GoogleSyncCalcPullResult.model_validate(_base_pull_payload())

    assert _casilla_id_from_payload(payload.operator_edits[0].casilla_id) == _INGRESOS_CASILLA


def test_google_calc_compute_payload_types_casilla_rows() -> None:
    payload = GoogleSyncCalcComputeResult.model_validate(_base_compute_payload())

    assert _casilla_id_from_payload(payload.computed[0].casilla_id) == _RENDIMIENTO_NETO_CASILLA


def test_google_calc_pull_payload_rejects_invalid_casilla_ids() -> None:
    raw = _base_pull_payload()
    raw["operator_edits"] = [{"casilla_id": _EMPTY_CASILLA_ID, "label": "Ingresos", "value": "100.00"}]

    with pytest.raises(ValidationError):
        GoogleSyncCalcPullResult.model_validate(raw)


def test_google_calc_pull_payload_rejects_generic_casilla_key() -> None:
    raw = _base_pull_payload()
    raw["operator_edits"] = [{"casilla": _INGRESOS_CASILLA, "label": "Ingresos", "value": "100.00"}]

    with pytest.raises(ValidationError):
        GoogleSyncCalcPullResult.model_validate(raw)


def test_google_calc_verify_payload_emits_casilla_id() -> None:
    payload = GoogleSyncCalcVerifyResult.model_validate(
        {
            "profile": "default",
            "modelo": "130",
            "revision": "2019-y-siguientes",
            "period": "1T",
            "year": 2025,
            "spreadsheet_id": "spreadsheet-id",
            "spreadsheet_url": "https://docs.google.test/spreadsheets/d/spreadsheet-id",
            "verdict": "mismatch",
            "aeat_oracle_present": False,
            "computed_count": 1,
            "divergence_count": 1,
            "divergences": [
                {
                    "casilla_id": _RENDIMIENTO_NETO_CASILLA,
                    "label": "Rendimiento neto",
                    "local": "20.00",
                    "sheets": "21.00",
                },
            ],
        },
    )

    assert _casilla_id_from_payload(payload.divergences[0].casilla_id) == _RENDIMIENTO_NETO_CASILLA


def test_google_calc_verify_payload_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        GoogleSyncCalcVerifyResult.model_validate(
            {
                "profile": "default",
                "modelo": "130",
                "revision": "2019-y-siguientes",
                "period": "1T",
                "year": 2025,
                "spreadsheet_id": "spreadsheet-id",
                "spreadsheet_url": "https://docs.google.test/spreadsheets/d/spreadsheet-id",
                "verdict": "mismatch",
                "aeat_oracle_present": False,
                "computed_count": 1,
                "divergence_count": 1,
                "divergences": [
                    {
                        "casilla": _RENDIMIENTO_NETO_CASILLA,
                        "label": "Rendimiento neto",
                        "local": "20.00",
                        "sheets": "21.00",
                    },
                ],
            },
        )


def test_google_calc_compute_payload_rejects_computed_rows_without_provenance() -> None:
    raw = _base_compute_payload()
    raw["computed"] = [
        {
            "casilla_id": _RENDIMIENTO_NETO_CASILLA,
            "value": "20.00",
            "formula_id": "m130-test-formula",
            "legal_refs": [],
            "source_refs": [_SOURCE_REF],
        },
    ]

    with pytest.raises(ValidationError):
        GoogleSyncCalcComputeResult.model_validate(raw)

    raw = _base_compute_payload()
    raw["computed"] = [
        {
            "casilla_id": _RENDIMIENTO_NETO_CASILLA,
            "value": "20.00",
            "formula_id": "m130-test-formula",
            "legal_refs": [_LEGAL_REF],
        },
    ]

    with pytest.raises(ValidationError):
        GoogleSyncCalcComputeResult.model_validate(raw)

    raw = _base_compute_payload()
    raw["computed"] = [{"casilla_id": _EMPTY_CASILLA_ID, "value": "20.00", "formula_id": "m130-test-formula"}]

    with pytest.raises(ValidationError):
        GoogleSyncCalcComputeResult.model_validate(raw)
