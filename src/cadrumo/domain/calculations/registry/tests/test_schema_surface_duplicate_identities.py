"""Duplicate registry identities retain strict refusal without repeated list scans."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..errors import RegistryValidationError
from ..schema import ModeloRevision
from ..schema_surfaces import (
    CalculationCompletenessCasilla,
    CasillaContinuidadEvolutionDefinition,
    validate_family_identity_uniqueness,
)
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    completeness_manifest,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla(identifier: str, number: str, segmento: str | None = None) -> CalculationCompletenessCasilla:
    return CalculationCompletenessCasilla(casilla_id=identifier, number=number, segmento=segmento)


def test_manifest_duplicate_ids_keep_sorted_complete_refusal() -> None:
    casillas = (
        _casilla("zeta", "1"),
        _casilla("alpha", "2"),
        _casilla("zeta", "3"),
        _casilla("alpha", "4"),
        _casilla("zeta", "5"),
    )
    with pytest.raises(ValidationError) as refused:
        completeness_manifest(casillas)

    assert refused.value.errors()[0]["msg"] == (
        "Value error, calculation-completeness manifest declares duplicate casilla ids: 'alpha', 'zeta'"
    )


@pytest.mark.parametrize("segmento", (None, "segment-a"))
def test_manifest_duplicate_record_metadata_keeps_sorted_refusal(segmento: str | None) -> None:
    casillas = (
        _casilla("one", "20", segmento),
        _casilla("two", "10", segmento),
        _casilla("three", "20", segmento),
        _casilla("four", "10", segmento),
    )
    with pytest.raises(ValidationError) as refused:
        completeness_manifest(casillas)

    expected = (
        "'10', '20'" if segmento is None else "'10' within segmento 'segment-a', '20' within segmento 'segment-a'"
    )
    assert refused.value.errors()[0]["msg"] == (
        f"Value error, calculation-completeness manifest declares duplicate casilla record-design metadata: {expected}"
    )


def test_manifest_allows_same_number_in_distinct_record_segments() -> None:
    casillas = (_casilla("one", "1"), _casilla("two", "1", "segment-a"), _casilla("three", "1", "segment-b"))
    manifest = completeness_manifest(casillas)

    assert manifest.casillas == casillas


def test_manifest_empty_population_is_still_refused() -> None:
    with pytest.raises(ValidationError) as refused:
        completeness_manifest(())

    assert refused.value.errors()[0]["msg"] == (
        "Value error, calculation-completeness manifest must enumerate at least one casilla"
    )


@pytest.mark.parametrize("identifier", (True, 1, 1.0))
def test_manifest_identifier_retains_strict_string_validation(identifier: object) -> None:
    with pytest.raises(ValidationError) as refused:
        CalculationCompletenessCasilla.model_validate({"casilla_id": identifier, "number": "1"})

    assert refused.value.errors()[0]["type"] == "string_type"


@pytest.mark.parametrize(
    "family", ("projection_endpoints", "verification_predicates", "casilla_continuidad_evolutions")
)
def test_family_duplicates_keep_sorted_complete_refusal(family: str) -> None:
    identities = ["zeta", "alpha", "zeta", "alpha", "zeta"]
    with pytest.raises(RegistryValidationError) as refused:
        validate_family_identity_uniqueness(family, identities)

    assert str(refused.value) == f"{family} declares duplicate ids: 'alpha', 'zeta'"
    assert identities == ["zeta", "alpha", "zeta", "alpha", "zeta"]


@pytest.mark.parametrize("identities", ((), ("only",), ("alpha", "zeta")))
def test_family_unique_population_is_preserved(identities: tuple[str, ...]) -> None:
    validate_family_identity_uniqueness("casilla_continuidad_evolutions", identities)


def test_revision_strict_model_refuses_duplicate_continuity_evolution_ids() -> None:
    def evolution(identifier: str) -> CasillaContinuidadEvolutionDefinition:
        return CasillaContinuidadEvolutionDefinition(
            id=identifier,
            continuidad_id="test-chain",
            from_revision="earlier",
            to_revision="test-revision",
            evolution_kind="unchanged",
            legal_refs=(REFERENCE_LEGAL_ID,),
            source_refs=(REFERENCE_SOURCE_ID,),
        )

    revision = minimal_revision().model_copy(
        update={
            "casilla_continuidad_evolutions": (
                evolution("zeta"),
                evolution("alpha"),
                evolution("zeta"),
                evolution("alpha"),
            )
        }
    )
    with pytest.raises(ValidationError) as refused:
        ModeloRevision.model_validate(revision)

    assert refused.value.errors()[0]["msg"] == (
        "Value error, casilla_continuidad_evolutions declares duplicate ids: 'alpha', 'zeta'"
    )
