"""Invalid observation requests report useful fields without echoing inputs."""

import json

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.frontend_requests import OperationObservationRequestV1

from ..request_diagnostics import request_faults

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_missing_observation_fields_are_named_without_exposing_unknown_fields() -> None:
    with pytest.raises(ValidationError) as caught:
        OperationObservationRequestV1.model_validate({"private-field": "private-value"})
    faults = request_faults("observe", caught.value)
    assert {"field": "after_cursor", "reason": "missing"} in faults
    assert {"field": "page_limit", "reason": "missing"} in faults
    encoded = json.dumps(faults)
    assert "private-field" not in encoded
    assert "private-value" not in encoded
    assert len(faults) <= 8
