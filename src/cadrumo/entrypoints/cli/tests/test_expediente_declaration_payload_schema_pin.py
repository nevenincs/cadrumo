"""Pin the advertised schema for an expediente declaration identifier."""

from __future__ import annotations

import pytest

from .._app_live_expedientes_payloads import ExpedienteDeclarationPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_expediente_id_is_required_and_advertises_the_pinned_aeat_shape() -> None:
    """The schema requires and constrains the declaration's expediente id."""
    schema = ExpedienteDeclarationPayload.model_json_schema()
    assert "expediente_id" in schema["required"]
    assert schema["properties"]["expediente_id"] == {
        "title": "Expediente Id",
        "type": "string",
        "minLength": 12,
        "maxLength": 32,
        "pattern": r"^[0-9]{4,}[A-Z0-9]+$",
    }
