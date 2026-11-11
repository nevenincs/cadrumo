"""Input-shape contracts for the transaction participation index models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ..codes import ModeloCode
from ..participation_index import TransactionRevisionParticipation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _participation_payload() -> dict[str, object]:
    return {
        "calculation_revision_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "modelo": "303",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "revision_state": "verificado",
    }


def test_participation_model_normalizes_a_string_modelo() -> None:
    participation = TransactionRevisionParticipation.model_validate(_participation_payload())

    assert participation.modelo == ModeloCode("303")
    assert isinstance(participation.modelo, ModeloCode)


def test_adapter_invalid_mapping_falls_through_to_model_validation() -> None:
    payload: dict[object, object] = {**_participation_payload(), 1: "extra key"}

    with pytest.raises(ValidationError) as exc_info:
        TransactionRevisionParticipation.model_validate(payload)

    error = exc_info.value.errors()[0]
    assert error["type"] == "invalid_key"
    assert error["loc"] == (1,)
