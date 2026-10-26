from __future__ import annotations

import pytest

from .....core.hashing import content_hash_hex
from ..authority_artifact import (
    AuthorityComponentKind,
    AuthorityGenerationPin,
    EvidenceComponentQuery,
    ProfileSchemaComponentQuery,
)
from .authority_fakes import FakeAuthorityComponentReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_component_reader_requires_its_exact_generation_pin() -> None:
    query = ProfileSchemaComponentQuery()
    reader = FakeAuthorityComponentReader({query: "profile-schema"})

    assert reader.load(query, pin=reader.pin()) == "profile-schema"
    assert reader.loads == [query]

    foreign = AuthorityGenerationPin(
        reader.logical_generation,
        content_hash_hex({"reader": "other"}),
    )
    with pytest.raises(RuntimeError, match="stale or foreign"):
        reader.load(query, pin=foreign)


def test_evidence_query_refuses_a_non_evidence_component_kind() -> None:
    with pytest.raises(ValueError, match="evidence queries require"):
        EvidenceComponentQuery("source", AuthorityComponentKind.GOVERNED_FACT)
