"""The ``ServiceCapability`` enum is the single authority for capability ids.

Asserts the enum members agree with the profile-schema ``capabilities`` section
(one fact field per member) and with the resolver/doctor that consume them, so a
capability cannot drift between the enum, the schema, and the gates.
"""

from __future__ import annotations

import pytest

from ...domain.user_profile.loader import load_user_profile_schema
from ..capabilities import ServiceCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _capabilities_section():
    schema = load_user_profile_schema()
    section = next((s for s in schema.sections if s.key == "capabilities"), None)
    assert section is not None, "the profile schema must carry a capabilities section"
    return section


def test_capability_schema_paths_are_dotted_under_capabilities() -> None:
    for capability in ServiceCapability:
        assert capability.schema_path == f"capabilities.{capability.value}"


def test_default_posture_is_conservative_for_cloud_only() -> None:
    # Cloud evidence upload (the regulated, sensitive path) defaults OFF; the
    # on-host / offline-capable capabilities default ON.
    for capability, expected in (
        (ServiceCapability.LLM_VISION, True),
        (ServiceCapability.GOOGLE_EXPORT, True),
    ):
        assert capability.default_enabled is expected


def test_every_capability_has_a_boolean_schema_field() -> None:
    section = _capabilities_section()
    field_keys = {field.key: field for field in section.fields}
    for capability in ServiceCapability:
        field = field_keys.get(capability.value)
        assert field is not None, f"missing schema field for {capability.value}"
        assert field.type.value == "boolean"


def test_no_orphan_capability_schema_field() -> None:
    # The reverse parity: every boolean field in the capabilities section is a
    # known enum member (no schema field without an enum identity).
    section = _capabilities_section()
    enum_values = {capability.value for capability in ServiceCapability}
    for field in section.fields:
        assert field.key in enum_values, f"schema field {field.key} has no ServiceCapability member"
