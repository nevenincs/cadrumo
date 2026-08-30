"""Google CLI payload schema guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core import CasillaId, validated_casilla_id
from .._modelo_spreadsheet_payloads import (
    ModeloSpreadsheetCalculateResult,
    ModeloSpreadsheetPullResult,
    ModeloSpreadsheetVerifyResult,
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
    payload = ModeloSpreadsheetPullResult.model_validate(_base_pull_payload())

    assert _casilla_id_from_payload(payload.operator_edits[0].casilla_id) == _INGRESOS_CASILLA


def test_google_calc_compute_payload_types_casilla_rows() -> None:
    payload = ModeloSpreadsheetCalculateResult.model_validate(_base_compute_payload())

    assert _casilla_id_from_payload(payload.computed[0].casilla_id) == _RENDIMIENTO_NETO_CASILLA


def test_google_calc_pull_payload_rejects_invalid_casilla_ids() -> None:
    raw = _base_pull_payload()
    raw["operator_edits"] = [{"casilla_id": _EMPTY_CASILLA_ID, "label": "Ingresos", "value": "100.00"}]

    with pytest.raises(ValidationError):
        ModeloSpreadsheetPullResult.model_validate(raw)


def test_google_calc_pull_payload_rejects_generic_casilla_key() -> None:
    raw = _base_pull_payload()
    raw["operator_edits"] = [{"casilla": _INGRESOS_CASILLA, "label": "Ingresos", "value": "100.00"}]

    with pytest.raises(ValidationError):
        ModeloSpreadsheetPullResult.model_validate(raw)


def test_google_calc_verify_payload_emits_casilla_id() -> None:
    payload = ModeloSpreadsheetVerifyResult.model_validate(
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
        ModeloSpreadsheetVerifyResult.model_validate(
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
        ModeloSpreadsheetCalculateResult.model_validate(raw)

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
        ModeloSpreadsheetCalculateResult.model_validate(raw)

    raw = _base_compute_payload()
    raw["computed"] = [{"casilla_id": _EMPTY_CASILLA_ID, "value": "20.00", "formula_id": "m130-test-formula"}]

    with pytest.raises(ValidationError):
        ModeloSpreadsheetCalculateResult.model_validate(raw)


class TestPullRelationEditGrounding:
    """A pulled relation reaches the operator with the grounding the pull recovered.

    The adapter recovers a relation's provenance, source modelo / filing year /
    periods / casillas, legal and source references and resolution instant from
    the workbook's developer metadata. This surface emitted only
    ``{relation, value}``, so all of it was discarded AFTER a typed pull had
    already established it — a number arriving with nothing saying where it came
    from, when the same value can be a local filing's carry, a live AEAT read or
    a hand edit, and only the provenance tells them apart.

    The projection is exercised through the adapter's own
    :func:`relation_edit_payload`, so what is asserted is the real emit path
    rather than a restated dict.
    """

    def test_every_recovered_grounding_field_survives_the_projection(self) -> None:
        from datetime import UTC, datetime
        from decimal import Decimal

        from ....adapters.outbound.google.calc_sheets_pull import relation_edit_payload
        from ....adapters.outbound.google.calc_sheets_pull import RelationEdit

        edit = RelationEdit(
            relation="m130-cuota-carry",
            value=Decimal("1234.56"),
            provenance="local_filing",
            source_modelo="180",
            source_filing_year=2025,
            source_periods=("1T", "2T"),
            source_casilla_ids=(_INGRESOS_CASILLA,),
            legal_refs=(_LEGAL_REF,),
            source_refs=(_SOURCE_REF,),
            resolved_at=datetime(2026, 3, 1, 9, 30, tzinfo=UTC),
        )

        raw = _base_pull_payload()
        raw["relation_edits_populated"] = 1
        raw["relation_edits"] = [relation_edit_payload(edit)]
        result = ModeloSpreadsheetPullResult.model_validate(raw)

        (row,) = result.relation_edits
        assert row.relation == "m130-cuota-carry"
        # Rendered as a string, not a JSON float: this figure reaches a filing.
        assert row.value == "1234.56"
        assert row.provenance == "local_filing"
        assert row.source_modelo == "180"
        assert row.source_filing_year == 2025
        assert row.source_periods == ["1T", "2T"]
        assert row.source_casilla_ids == [_INGRESOS_CASILLA]
        assert row.legal_refs == [_LEGAL_REF]
        assert row.source_refs == [_SOURCE_REF]
        assert row.resolved_at == "2026-03-01T09:30:00+00:00"

    def test_a_manually_edited_relation_carries_no_invented_grounding(self) -> None:
        """A relation edited without an apply round-trip genuinely has none.

        The optional fields must stay absent rather than acquire defaults that
        would assert a provenance the workbook never recorded.
        """
        from ....adapters.outbound.google.calc_sheets_pull import relation_edit_payload
        from ....adapters.outbound.google.calc_sheets_pull import RelationEdit

        raw = _base_pull_payload()
        raw["relation_edits_populated"] = 1
        raw["relation_edits"] = [relation_edit_payload(RelationEdit(relation="m130-cuota-carry"))]
        result = ModeloSpreadsheetPullResult.model_validate(raw)

        (row,) = result.relation_edits
        assert row.provenance is None
        assert row.resolved_at is None
        assert row.source_modelo is None
        assert row.source_periods == []
        assert row.legal_refs == []

    def test_an_unknown_provenance_token_is_refused(self) -> None:
        """The provenance set is closed, so the transport cannot widen it."""
        raw = _base_pull_payload()
        raw["relation_edits_populated"] = 1
        raw["relation_edits"] = [{"relation": "m130-cuota-carry", "provenance": "guessed"}]

        with pytest.raises(ValidationError):
            ModeloSpreadsheetPullResult.model_validate(raw)

    def test_a_malformed_casilla_reference_is_refused(self) -> None:
        """Grounding is typed, so an anonymous casilla string cannot ride along."""
        raw = _base_pull_payload()
        raw["relation_edits_populated"] = 1
        raw["relation_edits"] = [{"relation": "m130-cuota-carry", "source_casilla_ids": [_EMPTY_CASILLA_ID]}]

        with pytest.raises(ValidationError):
            ModeloSpreadsheetPullResult.model_validate(raw)
