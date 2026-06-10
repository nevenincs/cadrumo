"""Real-behaviour roundtrip tests for modelo CLI payload schemas.

``CalculationRevisionPayload.inputs_snapshot`` was typed as
``dict[str, object]`` while the domain source (``CalculationRevision``)
and the application constructor both produce ``dict[str, str]``
(canonical Decimal strings). These tests pin the corrected
``dict[str, str]`` contract at the CLI wire boundary for
``CalculationRevisionPayload``, ``WorkCalculateResult``, and
``WorkRevisionResult``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

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


def _base_revision_fields() -> dict[str, Any]:
    return dict(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        state="BORRADOR",
        casilla_values={"001": "1234.56"},
        observations=(
            ObservationPayload(
                casilla_id="001",
                value="1234.56",
                formula_id="f1",
                legal_refs=("art-1",),
                source_refs=("libro-1",),
            ),
        ),
        binding_overrides={"src1": "ledger-abc"},
        inputs_snapshot={"ejercicio": "2024", "periodo": "1T"},
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# CalculationRevisionPayload
# ---------------------------------------------------------------------------


def test_calculation_revision_payload_inputs_snapshot_roundtrips() -> None:
    """inputs_snapshot dict[str,str] survives model_dump_json / model_validate_json."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    json_str = original.model_dump_json()
    restored = CalculationRevisionPayload.model_validate_json(json_str)

    assert restored == original
    assert restored.inputs_snapshot == {"ejercicio": "2024", "periodo": "1T"}


def test_calculation_revision_payload_inputs_snapshot_rejects_non_string_values() -> None:
    """Strict pydantic must reject a non-string value in inputs_snapshot."""
    fields = _base_revision_fields()
    # Inject an integer value — must not pass dict[str, str] validation.
    fields["inputs_snapshot"] = {"ejercicio": 2024}  # type: ignore[dict-item]

    with pytest.raises(ValidationError):
        CalculationRevisionPayload(**fields)


def test_calculation_revision_payload_inputs_snapshot_json_channel_rejects_non_string() -> None:
    """Non-string value injected via raw JSON string must also be rejected."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["inputs_snapshot"] = {"ejercicio": 2024}

    with pytest.raises(ValidationError):
        CalculationRevisionPayload.model_validate(raw)


# ---------------------------------------------------------------------------
# WorkCalculateResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_calculate_result_inputs_snapshot_roundtrips() -> None:
    """WorkCalculateResult.inputs_snapshot dict[str,str] roundtrips through JSON."""
    payload = WorkCalculateResult(
        saved=True,
        saved_confirmation="Saved revision a" * 2,
        **_base_revision_fields(),
    )
    restored = WorkCalculateResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.inputs_snapshot, dict)
    assert all(isinstance(v, str) for v in restored.inputs_snapshot.values())


def test_work_calculate_result_inputs_snapshot_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["inputs_snapshot"] = {"ejercicio": 2024}  # type: ignore[dict-item]

    with pytest.raises(ValidationError):
        WorkCalculateResult(
            saved=True,
            saved_confirmation="Saved",
            **fields,
        )


# ---------------------------------------------------------------------------
# WorkRevisionResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_revision_result_inputs_snapshot_roundtrips() -> None:
    """WorkRevisionResult.inputs_snapshot dict[str,str] roundtrips through JSON."""
    payload = WorkRevisionResult(**_base_revision_fields())
    restored = WorkRevisionResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.inputs_snapshot, dict)
    assert all(isinstance(v, str) for v in restored.inputs_snapshot.values())


def test_work_revision_result_inputs_snapshot_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["inputs_snapshot"] = {"ejercicio": 2024}  # type: ignore[dict-item]

    with pytest.raises(ValidationError):
        WorkRevisionResult(**fields)


# ---------------------------------------------------------------------------
# Anti-tautology proof: mutate persisted JSON, assert strict inequality
# ---------------------------------------------------------------------------


def test_anti_tautology_mutated_inputs_snapshot_surfaces_inequality() -> None:
    """Mutating an inputs_snapshot value in the JSON blob produces a different model."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["inputs_snapshot"]["ejercicio"] = "2023"  # mutate one value

    # Re-serialise to a JSON string so tuple fields survive model_validate_json.
    restored = CalculationRevisionPayload.model_validate_json(json.dumps(raw))

    assert restored != original
    assert restored.inputs_snapshot["ejercicio"] == "2023"
    assert original.inputs_snapshot["ejercicio"] == "2024"
