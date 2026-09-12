"""The ``ServiceCapability`` enum is the single authority for capability ids.

Asserts the enum members agree with the profile-schema ``capabilities`` section
(one fact field per member) and with the resolver/doctor that consume them, so a
capability cannot drift between the enum, the schema, and the gates.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from ..capabilities import ServiceCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _capabilities_section():
    schema_path = (
        Path(__file__).resolve().parents[2] / "_data" / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    )
    payload = tomllib.loads(schema_path.read_text(encoding="utf-8"))
    sections = payload.get("sections")
    assert isinstance(sections, list), "the profile schema must carry sections"
    section = next((candidate for candidate in sections if candidate.get("key") == "capabilities"), None)
    assert isinstance(section, dict), "the profile schema must carry a capabilities section"
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
    fields = section.get("fields")
    assert isinstance(fields, list), "the capabilities section must carry fields"
    field_keys = {field["key"]: field for field in fields}
    for capability in ServiceCapability:
        field = field_keys.get(capability.value)
        assert field is not None, f"missing schema field for {capability.value}"
        assert field["type"] == "boolean"


def test_no_orphan_capability_schema_field() -> None:
    # The reverse parity: every boolean field in the capabilities section is a
    # known enum member (no schema field without an enum identity).
    section = _capabilities_section()
    enum_values = {capability.value for capability in ServiceCapability}
    fields = section.get("fields")
    assert isinstance(fields, list), "the capabilities section must carry fields"
    for field in fields:
        assert field["key"] in enum_values, f"schema field {field['key']} has no ServiceCapability member"
