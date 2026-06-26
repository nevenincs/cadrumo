"""Real-behaviour roundtrip tests for modelo CLI payload schemas.

``CalculationRevisionPayload.input_values_by_casilla_id`` was typed as
``dict[str, object]`` while the domain source (``CalculationRevision``)
and the application constructor both produce ``dict[CasillaId, str]``
(canonical casilla ids with canonical Decimal/string values). These
tests pin the corrected ``dict[CasillaId, str]`` contract at the CLI wire boundary for
``CalculationRevisionPayload``, ``WorkCalculateResult``, and
``WorkRevisionResult``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import CasillaId, RelationId, validated_casilla_id
from .._modelo_payloads import (
    CalculationRevisionPayload,
    ObservationPayload,
    WorkCalculateResult,
    WorkRevisionResult,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REVISION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_NOW = "2025-01-01T00:00:00+00:00"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_PAYLOAD_CASILLA: CasillaId = _casilla_id("001")
_INPUT_EJERCICIO_CASILLA: CasillaId = _casilla_id("ejercicio")
_INPUT_PERIODO_CASILLA: CasillaId = _casilla_id("periodo")
_NON_CANONICAL_KEY = "bad key"
_RELATION_OVERRIDE: RelationId = "renta-2024-rel-130-pagos-fraccionados"


def _base_revision_fields() -> dict[str, Any]:
    return dict(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        state="BORRADOR",
        casilla_values={_PAYLOAD_CASILLA: "1234.56"},
        observations=(
            ObservationPayload(
                casilla_id=_PAYLOAD_CASILLA,
                value="1234.56",
                formula_id="f1",
                legal_refs=("art-1",),
                operand_refs=(_PAYLOAD_CASILLA, "iva.rate"),
                operand_casilla_refs=(_PAYLOAD_CASILLA,),
                source_refs=("libro-1",),
            ),
        ),
        binding_overrides={"src1": "ledger-abc"},
        relation_overrides={_RELATION_OVERRIDE: "725.75"},
        input_values_by_casilla_id={_INPUT_EJERCICIO_CASILLA: "2024", _INPUT_PERIODO_CASILLA: "1T"},
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# CalculationRevisionPayload
# ---------------------------------------------------------------------------


def test_calculation_revision_payload_input_values_by_casilla_id_roundtrips() -> None:
    """input_values_by_casilla_id dict[CasillaId, str] survives model_dump_json / model_validate_json."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    json_str = original.model_dump_json()
    restored = CalculationRevisionPayload.model_validate_json(json_str)

    assert restored == original
    assert restored.input_values_by_casilla_id == {_INPUT_EJERCICIO_CASILLA: "2024", _INPUT_PERIODO_CASILLA: "1T"}
    assert restored.relation_overrides == {_RELATION_OVERRIDE: "725.75"}


def test_calculation_revision_payload_input_values_by_casilla_id_rejects_non_string_values() -> None:
    """Strict pydantic must reject a non-string value in input_values_by_casilla_id."""
    fields = _base_revision_fields()
    # Inject an integer value - must not pass dict[CasillaId, str] validation.
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        CalculationRevisionPayload(**fields)


def test_calculation_revision_payload_input_values_by_casilla_id_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_NON_CANONICAL_KEY: "2024"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload(**fields)


def test_calculation_revision_payload_casilla_values_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload(**fields)


def test_observation_payload_rejects_non_canonical_casilla_id() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        ObservationPayload(
            casilla_id=_NON_CANONICAL_KEY,
            value="1234.56",
            legal_refs=("art-1",),
            source_refs=("libro-1",),
        )


def test_observation_payload_rejects_non_canonical_operand_casilla_ref() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        ObservationPayload(
            casilla_id=_PAYLOAD_CASILLA,
            value="1234.56",
            operand_refs=("iva.rate",),
            operand_casilla_refs=(_NON_CANONICAL_KEY,),
            legal_refs=("art-1",),
            source_refs=("libro-1",),
        )


def test_observation_payload_rejects_untraced_operand_casilla_ref() -> None:
    with pytest.raises(ValidationError, match="declares operand_casilla_refs"):
        ObservationPayload(
            casilla_id=_PAYLOAD_CASILLA,
            value="1234.56",
            operand_refs=("iva.rate",),
            operand_casilla_refs=(_PAYLOAD_CASILLA,),
            legal_refs=("art-1",),
            source_refs=("libro-1",),
        )


def test_calculation_revision_payload_input_values_by_casilla_id_json_channel_rejects_non_string() -> None:
    """Non-string value injected via raw JSON string must also be rejected."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        CalculationRevisionPayload.model_validate(raw)


def test_calculation_revision_payload_json_channel_rejects_non_canonical_casilla_key() -> None:
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload.model_validate_json(json.dumps(raw))


# ---------------------------------------------------------------------------
# WorkCalculateResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_calculate_result_input_values_by_casilla_id_roundtrips() -> None:
    """WorkCalculateResult.input_values_by_casilla_id dict[CasillaId, str] roundtrips through JSON."""
    payload = WorkCalculateResult(
        saved=True,
        saved_confirmation="Saved revision a" * 2,
        **_base_revision_fields(),
    )
    restored = WorkCalculateResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.input_values_by_casilla_id, dict)
    assert all(isinstance(v, str) for v in restored.input_values_by_casilla_id.values())


def test_work_calculate_result_input_values_by_casilla_id_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        WorkCalculateResult(
            saved=True,
            saved_confirmation="Saved",
            **fields,
        )


def test_work_calculate_result_input_values_by_casilla_id_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_NON_CANONICAL_KEY: "2024"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        WorkCalculateResult(
            saved=True,
            saved_confirmation="Saved",
            **fields,
        )


# ---------------------------------------------------------------------------
# WorkRevisionResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_revision_result_input_values_by_casilla_id_roundtrips() -> None:
    """WorkRevisionResult.input_values_by_casilla_id dict[CasillaId, str] roundtrips through JSON."""
    payload = WorkRevisionResult(**_base_revision_fields())
    restored = WorkRevisionResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.input_values_by_casilla_id, dict)
    assert all(isinstance(v, str) for v in restored.input_values_by_casilla_id.values())


def test_work_revision_result_input_values_by_casilla_id_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        WorkRevisionResult(**fields)


def test_work_revision_result_casilla_values_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        WorkRevisionResult(**fields)
