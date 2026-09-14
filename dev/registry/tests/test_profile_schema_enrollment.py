"""Captured profile-schema source enrollment contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.profile_schema import capture_profile_schema, parse_captured_profile_schema
from ..pipeline.authority_publication import authority_candidate_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCHEMA = b"""[schema]
id = "cadrumo.user_profile"
version = 1
title = "Synthetic profile schema"
snapshot_policy = "immutable_secure_snapshot_hash"
remove_policy = "live_profile_tombstone_retain_snapshots"

[[sections]]
key = "identity"
title = "Synthetic identity"
sensitivity = "identity"

[[sections.fields]]
key = "name"
type = "string"
sensitivity = "identity"
description = "Synthetic name"
legal_refs = ["law:one"]
"""


def test_captured_profile_schema_refuses_unknown_envelope_member() -> None:
    with pytest.raises(RegistryValidationError, match=r"unexpected=.*shadow"):
        parse_captured_profile_schema(
            _SCHEMA + b"\n[shadow]\nvalue = 1\n",
            source_path=Path("schema.toml"),
        )


def test_captured_profile_schema_refuses_unknown_legal_reference() -> None:
    with pytest.raises(RegistryValidationError, match=r"unknown legal references.*law:one"):
        parse_captured_profile_schema(
            _SCHEMA,
            source_path=Path("schema.toml"),
            legal_reference_ids=frozenset(),
        )


def test_capture_requires_the_explicit_profile_source(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="unavailable"):
        capture_profile_schema(tmp_path / "missing.toml")


def test_profile_source_bytes_participate_in_candidate_identity(tmp_path: Path) -> None:
    profile = tmp_path / "schema.toml"
    profile.write_bytes(_SCHEMA)
    inputs = {
        "registry_root": bundled_path("registry", "aeat"),
        "source_root": bundled_path(),
        "profile_schema_path": profile,
    }
    before = authority_candidate_identity(**inputs)
    profile.write_bytes(_SCHEMA.replace(b"Synthetic profile schema", b"Changed synthetic profile schema"))

    assert authority_candidate_identity(**inputs) != before
