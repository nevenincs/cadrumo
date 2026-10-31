"""Published snapshot globals carry the facts their typed decode actually reads."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityComponentCodecError,
    GovernedFactComponentQuery,
    SnapshotGlobalsComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_component_codec import (
    decode_authority_component,
    encode_authority_component,
)
from cadrumo.domain.calculations.registry.snapshot_globals import SnapshotGlobalCatalogues

from ..authority import compiled_bundled_authority
from ..authority_database import _decoded_fact_dependencies

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_snapshot_globals_enrolls_the_fact_required_by_annual_orden_validation() -> None:
    catalogues = compiled_bundled_authority().catalogues
    globals_value = SnapshotGlobalCatalogues.from_catalogues(catalogues)
    assert globals_value.supplementary_ordenes, "the test must exercise the annual Orden projections"
    query = SnapshotGlobalsComponentQuery()
    payload = encode_authority_component(query, globals_value)
    facts = catalogues.facts.facts
    fact_queries = tuple(GovernedFactComponentQuery(fact_id) for fact_id in sorted(facts))
    fact_values = tuple(facts[item.fact_id] for item in fact_queries)

    dependencies = _decoded_fact_dependencies(query, payload, fact_queries, fact_values)

    assert GovernedFactComponentQuery("form-row-codes") in dependencies
    admitted = tuple(facts[item.fact_id] for item in dependencies)
    decoded = decode_authority_component(query, payload, dependencies=admitted)
    assert decoded == globals_value
    without_row_codes = tuple(facts[item.fact_id] for item in dependencies if item.fact_id != "form-row-codes")
    with pytest.raises(AuthorityComponentCodecError, match="failed typed decoding"):
        decode_authority_component(query, payload, dependencies=without_row_codes)
