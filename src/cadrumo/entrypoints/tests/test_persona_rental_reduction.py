"""The art. 23.2 LIRPF rate of the let-dwelling persona is derived from its stated lease facts, never stated.

The lease is built from the persona's own facts, through the same row builder the replay submits and the
record reader the profile uses, and handed to the real derivation with the registry's dated regime data. Every
date turns on the registry: the regime start and the contract cut-off come from the regime fact, and the
exercises from the support envelope.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.rental_reduction import resolve_rental_reduction_art232_rules
from ...domain.calculations.registry.tests.authored_editions import authored_revisions, supported_authored_exercises
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_facts import arrendamiento_from_row
from ...domain.renta.rental_reduction_derivation import (
    TIER_50,
    RentalReductionArt232Rules,
    RentalReductionDerivation,
    RentalReductionRefusal,
    derive_rental_reduction,
)
from ...tests.personas import Persona, RentalProperty, read_persona
from .persona_materialisation import year_envelope
from .persona_rental_replay import lease_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA_ID = "arrendador-jubilado"
_MODELO = "100"
_PROPERTY_ROW = 0


def _revision_id_for(year: int) -> str:
    for revision in authored_revisions(_MODELO):
        last = revision.valid_to.year if revision.valid_to is not None else revision.valid_from.year
        if revision.valid_from.year <= year <= last:
            return revision.id
    raise LookupError(f"no authored Modelo 100 edition governs {year}")


def _rules(year: int, operation: PinnedAuthorityOperation) -> RentalReductionArt232Rules:
    return resolve_rental_reduction_art232_rules(
        revision_id=_revision_id_for(year), devengo=date(year, 12, 31), operation=operation
    )


def _persona(operation: PinnedAuthorityOperation) -> tuple[Persona, RentalProperty]:
    persona = read_persona(_PERSONA_ID, envelope=year_envelope(operation))
    (rental,) = persona.rental_properties
    return persona, rental


def _stated_lease(
    persona: Persona,
    rental: RentalProperty,
    operation: PinnedAuthorityOperation,
    *,
    contract: date | None = None,
    without: frozenset[str] = frozenset(),
) -> ArrendamientoRecord:
    """The lease the persona's facts record, optionally dated differently or missing stated facts."""
    row = {key: value for key, value in lease_row(persona, rental, _PROPERTY_ROW, year_envelope(operation))}
    if contract is not None:
        row["fecha_contrato"] = row["fecha_inicio"] = contract.isoformat()
    for leaf in without:
        del row[leaf]
    return arrendamiento_from_row(0, row)


def _devengo_years(operation: PinnedAuthorityOperation) -> tuple[list[int], list[int]]:
    """The supported exercises whose devengo falls before the regime start, and those on or after it."""
    legacy: list[int] = []
    tiered: list[int] = []
    for year in supported_authored_exercises(_MODELO):
        (legacy if date(year, 12, 31) < _rules(year, operation).regime_start else tiered).append(year)
    return legacy, tiered


def _derive(lease: ArrendamientoRecord, year: int, operation: PinnedAuthorityOperation) -> RentalReductionDerivation:
    return derive_rental_reduction((lease,), devengo=date(year, 12, 31), rules=_rules(year, operation))


def test_the_stated_lease_takes_the_legacy_rate_for_the_returns_before_the_regime_and_the_lower_tier_after_it(
    operation: PinnedAuthorityOperation,
) -> None:
    persona, rental = _persona(operation)
    lease = _stated_lease(persona, rental, operation)
    legacy_years, tiered_years = _devengo_years(operation)
    assert legacy_years
    assert tiered_years
    for year in (*legacy_years, *tiered_years):
        assert lease.fecha_contrato >= _rules(year, operation).contract_cut_off

    legacy = _rules(legacy_years[0], operation).legacy_tier
    assert {year: _derive(lease, year, operation).tier for year in legacy_years} == dict.fromkeys(legacy_years, legacy)
    assert {year: _derive(lease, year, operation).tier for year in tiered_years} == dict.fromkeys(tiered_years, TIER_50)


def test_a_contract_dated_before_the_cut_off_keeps_the_legacy_rate_in_every_return(
    operation: PinnedAuthorityOperation,
) -> None:
    persona, rental = _persona(operation)
    _, tiered_years = _devengo_years(operation)
    cut_off = _rules(tiered_years[0], operation).contract_cut_off
    lease = _stated_lease(persona, rental, operation, contract=cut_off - timedelta(days=1))

    legacy = _rules(tiered_years[0], operation).legacy_tier
    assert {year: _derive(lease, year, operation).tier for year in tiered_years} == dict.fromkeys(tiered_years, legacy)


@pytest.mark.parametrize(
    ("missing", "refusal"),
    [
        ("uso_vivienda", RentalReductionRefusal.USO_VIVIENDA_UNSTATED),
        ("zona_tensionada", RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED),
    ],
)
def test_a_lease_missing_a_deciding_fact_is_refused_and_never_defaults_to_a_tier(
    operation: PinnedAuthorityOperation, missing: str, refusal: RentalReductionRefusal
) -> None:
    persona, rental = _persona(operation)
    _, tiered_years = _devengo_years(operation)
    lease = _stated_lease(persona, rental, operation, without=frozenset({missing}))

    outcome = _derive(lease, tiered_years[0], operation)

    assert (outcome.aplicable, outcome.tier, outcome.refusal) == (None, None, refusal)
