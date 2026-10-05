"""Protocol versions require the exact current integer type on the wire."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ..contracts import RuntimeClientHello, RuntimeServerHello

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("version", [True, False, 2.0, "2", 0, 1, 3, None])
@pytest.mark.parametrize("server", [False, True])
def test_version_refuses_coerced_types_and_unsupported_values(version: object, server: bool) -> None:
    payload = {
        "protocol_version": version,
        "product_version": "synthetic-cohort",
        "storage_identity": "a" * 64,
    }
    if server:
        payload["boot_id"] = str(uuid4())
    model = RuntimeServerHello if server else RuntimeClientHello
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("server", [False, True])
def test_current_integer_version_is_accepted(server: bool) -> None:
    payload: dict[str, object] = {
        "protocol_version": 2,
        "product_version": "synthetic-cohort",
        "storage_identity": "a" * 64,
    }
    if server:
        payload["boot_id"] = str(uuid4())
    model = RuntimeServerHello if server else RuntimeClientHello
    assert model.model_validate_json(json.dumps(payload)).protocol_version == 2
