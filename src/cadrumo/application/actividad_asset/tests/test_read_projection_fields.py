"""Every field a read's public projection declares is carried out of its private result."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.registered_operations import _READS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENVELOPE = {"profile_id", "authority", "outcome", "refusal"}


@pytest.mark.parametrize("definition_id", sorted(_READS))
def test_a_read_carries_every_field_its_projection_declares(definition_id: str) -> None:
    _, result_type, projection_type, _, fields, _ = _READS[definition_id]

    assert set(projection_type.model_fields) - _ENVELOPE == set(fields)
    assert set(fields) <= set(result_type.model_fields)
