"""Application provenance tokens must remain schema-declared."""

from __future__ import annotations

import pytest

from ....domain.user_profile import declared_provenance_sources, load_user_profile_schema
from ..censo_sync import CENSO_SOURCE_TAG

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_censo_source_tag_is_declared_by_the_schema() -> None:
    """The Censo projection never stamps a provenance value the record rejects."""
    assert CENSO_SOURCE_TAG in declared_provenance_sources()


def test_declared_provenance_sources_are_read_from_the_schema() -> None:
    """The application validates against the schema authority, not a copy."""
    assert declared_provenance_sources() == frozenset(
        load_user_profile_schema().field("provenance.source").enum_values,
    )
