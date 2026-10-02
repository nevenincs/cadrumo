"""Closed CLI shape for one workstation capability row."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..check_payloads import CheckCapabilityPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_capability_row_keeps_the_established_public_fields() -> None:
    """The CLI capability projection keeps only its established fields."""
    assert set(CheckCapabilityPayload.model_fields) == {"capability", "enabled", "source"}
    with pytest.raises(ValidationError):
        CheckCapabilityPayload(capability="cloud_evidence_upload", enabled=False, source="default", reason="private")
