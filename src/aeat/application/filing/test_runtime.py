"""Structural tests for the registry casilla schema projection.

Asserts that legal_refs and source_refs survive the projection from
CasillaDefinition through to RegistryCasillaSchema so that filing-layer
consumers have access to regulatory grounding.

Modelo 130 is used as the reference fixture because it is fully validated
and representative of the registry's legal-grounding requirements.
"""

from __future__ import annotations

import pytest

from ...core.resources import resources
from .runtime import RegistryCasillaSchema, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TEST_MODELO = "130"
_TEST_YEAR = 2026
_TEST_PERIOD = "1T"


def _source_casilla_refs() -> dict[str, tuple[str, ...]]:
    """Return {casilla_id: legal_refs} from the authoritative CasillaDefinition."""
    snapshot = resources().modelos.authority.snapshot(_TEST_MODELO, filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    return {casilla.id: casilla.legal_refs for casilla in snapshot.revision.casillas}


def _source_casilla_source_refs() -> dict[str, tuple[str, ...]]:
    """Return {casilla_id: source_refs} from the authoritative CasillaDefinition."""
    snapshot = resources().modelos.authority.snapshot(_TEST_MODELO, filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    return {casilla.id: casilla.source_refs for casilla in snapshot.revision.casillas}


def test_legal_refs_survive_projection() -> None:
    """RegistryCasillaSchema must carry the same legal_refs as the source CasillaDefinition."""
    source = _source_casilla_refs()
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    collection = provider.get_collection(_TEST_MODELO)
    schemas = collection.all()

    casillas_with_refs = [s for s in schemas if source.get(s.id)]
    assert casillas_with_refs, f"No casillas with legal_refs found in modelo {_TEST_MODELO} — test would be vacuous"

    for schema in schemas:
        assert isinstance(schema, RegistryCasillaSchema)
        expected = source.get(schema.id, ())
        assert schema.legal_refs == expected, (
            f"legal_refs mismatch for casilla {schema.id}: projected={schema.legal_refs!r}, source={expected!r}"
        )


def test_source_refs_survive_projection() -> None:
    """RegistryCasillaSchema must carry the same source_refs as the source CasillaDefinition."""
    source = _source_casilla_source_refs()
    provider = build_runtime_schema_provider(modelos=[_TEST_MODELO], filing_year=_TEST_YEAR, period=_TEST_PERIOD)
    collection = provider.get_collection(_TEST_MODELO)
    schemas = collection.all()

    casillas_with_refs = [s for s in schemas if source.get(s.id)]
    assert casillas_with_refs, f"No casillas with source_refs found in modelo {_TEST_MODELO} — test would be vacuous"

    for schema in schemas:
        assert isinstance(schema, RegistryCasillaSchema)
        expected = source.get(schema.id, ())
        assert schema.source_refs == expected, (
            f"source_refs mismatch for casilla {schema.id}: projected={schema.source_refs!r}, source={expected!r}"
        )
