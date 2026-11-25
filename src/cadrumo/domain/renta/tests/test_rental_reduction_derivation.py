"""The art. 23.2 LIRPF reduction derived from a lease and the published regime data.

Every date the tests turn on is read off the registry: the regime start and the
contract cut-off from the regime fact, the rent threshold and the rehabilitation
look-back from the parameters, and the exercises from the support envelope.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.calendar_shift import shift_by_calendar_years
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.rental_reduction import (
    resolve_rental_reduction_art232_rules,
    resolve_rental_reduction_art232_tier_catalogue,
)
from ...calculations.registry.tests.authored_editions import authored_revisions, supported_authored_exercises
from ...contribuyente.arrendamiento_record import (
    ArrendamientoRecord,
    ArrendatarioEntidadFinalidad,
    ArrendatarioEntidadTipo,
    Inquilino,
    InquilinoEdad,
)
from ..rental_reduction_derivation import (
    TIER_50,
    TIER_60,
    TIER_70,
    TIER_90,
    RentalReductionArt232Rules,
    RentalReductionRefusal,
    derive_rental_reduction,
    leases_active_in,
)

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"


def _revision_id_for(year: int) -> str:
    for revision in authored_revisions(_MODELO):
        last = revision.valid_to.year if revision.valid_to is not None else revision.valid_from.year
        if revision.valid_from.year <= year <= last:
            return revision.id
    raise LookupError(f"no authored Modelo 100 edition governs {year}")


def _rules(year: int, operation: PinnedAuthorityOperation) -> RentalReductionArt232Rules:
    return resolve_rental_reduction_art232_rules(
        modelo_id=_MODELO, revision_id=_revision_id_for(year), devengo=date(year, 12, 31), operation=operation
    )


def _tiered_year(operation: PinnedAuthorityOperation) -> int:
    """The first supported exercise whose devengo falls in the tiered regime."""
    for year in supported_authored_exercises(_MODELO):
        if date(year, 12, 31) >= _rules(year, operation).regime_start:
            return year
    raise LookupError("no supported exercise falls in the tiered regime")


def _legacy_year(operation: PinnedAuthorityOperation) -> int:
    """The last supported exercise whose devengo falls before the regime start."""
    years = [
        year
        for year in supported_authored_exercises(_MODELO)
        if date(year, 12, 31) < _rules(year, operation).regime_start
    ]
    if not years:
        raise LookupError("no supported exercise falls before the regime start")
    return years[-1]


def _lease(contract: date, **facts: object) -> ArrendamientoRecord:
    values: dict[str, object] = {
        "clave": 0,
        "inmueble": 0,
        "fecha_contrato": contract,
        "fecha_inicio": contract,
        "uso_vivienda": True,
        "zona_tensionada": False,
    }
    values.update(facts)
    return ArrendamientoRecord.model_validate(values)


def _tenant(nif: str, band: InquilinoEdad) -> Inquilino:
    return Inquilino(nif=nif, franja_edad=band, extranjero=True)


@pytest.fixture
def tiered(authority_operation: PinnedAuthorityOperation) -> tuple[RentalReductionArt232Rules, date]:
    year = _tiered_year(authority_operation)
    return _rules(year, authority_operation), date(year, 12, 31)


def test_contract_the_day_before_the_cut_off_takes_the_legacy_rate_and_one_on_it_the_tiers(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    before = derive_rental_reduction(
        (_lease(rules.contract_cut_off - timedelta(days=1)),), devengo=devengo, rules=rules
    )
    on = derive_rental_reduction((_lease(rules.contract_cut_off),), devengo=devengo, rules=rules)
    assert (before.aplicable, before.tier) == (True, rules.legacy_tier)
    assert (on.aplicable, on.tier) == (True, TIER_50)


def test_a_devengo_before_the_regime_start_takes_the_legacy_rate_whatever_the_contract(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = _legacy_year(authority_operation)
    rules = _rules(year, authority_operation)
    contract = max(rules.contract_cut_off, date(year, 1, 1))
    lease = _lease(contract, zona_tensionada=True, incumple_lau_17_6=True)
    outcome = derive_rental_reduction((lease,), devengo=date(year, 12, 31), rules=rules)
    assert (outcome.aplicable, outcome.tier) == (True, rules.legacy_tier)


def test_legacy_contract_after_the_regime_start_keeps_the_legacy_rate(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    lease = _lease(
        rules.contract_cut_off - timedelta(days=1),
        zona_tensionada=True,
        incumple_lau_17_6=False,
        primer_arrendamiento_vivienda=True,
        inquilinos=(_tenant("X1234567", InquilinoEdad.DE_18_A_35),),
    )
    outcome = derive_rental_reduction((lease,), devengo=devengo, rules=rules)
    assert (outcome.aplicable, outcome.tier) == (True, rules.legacy_tier)


def test_each_tier_is_reached_by_the_facts_that_establish_it(
    tiered: tuple[RentalReductionArt232Rules, date],
    authority_operation: PinnedAuthorityOperation,
) -> None:
    rules, devengo = tiered
    contract = rules.contract_cut_off
    previous = Decimal("1000.00")
    cut = (previous * (Decimal(1) - rules.rebaja_threshold) - Decimal("0.01")).quantize(Decimal("0.01"))
    cases = {
        TIER_90: _lease(
            contract,
            zona_tensionada=True,
            incumple_lau_17_6=False,
            renta_inicial=cut,
            renta_ultima_contrato_anterior=previous,
        ),
        TIER_70: _lease(
            contract,
            zona_tensionada=True,
            incumple_lau_17_6=False,
            primer_arrendamiento_vivienda=True,
            inquilinos=(
                _tenant("X1234567", InquilinoEdad.DE_18_A_35),
                _tenant("Y7654321", InquilinoEdad.DE_18_A_35),
            ),
        ),
        TIER_60: _lease(
            contract,
            rehabilitacion_fecha=shift_by_calendar_years(contract, -rules.rehabilitation_lookback_years),
        ),
        TIER_50: _lease(contract),
    }
    for tier, lease in cases.items():
        outcome = derive_rental_reduction((lease,), devengo=devengo, rules=rules)
        assert (outcome.aplicable, outcome.tier) == (True, tier), tier
    catalogue = resolve_rental_reduction_art232_tier_catalogue(effective_date=devengo, authority=authority_operation)
    assert set(cases) == catalogue.all_tiers


def test_a_qualifying_public_tenant_reaches_seventy_per_cent(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    lease = _lease(
        rules.contract_cut_off,
        arrendatario_entidad_tipo=ArrendatarioEntidadTipo.ADMINISTRACION_PUBLICA,
        arrendatario_entidad_finalidad=ArrendatarioEntidadFinalidad.VIVIENDA_ASEQUIBLE_O_SOCIAL,
    )
    assert derive_rental_reduction((lease,), devengo=devengo, rules=rules).tier == TIER_70


def test_boundaries_of_the_rent_cut_and_the_rehabilitation_window_stay_at_the_lower_tier(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    contract = rules.contract_cut_off
    previous = Decimal("1000.00")
    exactly_threshold = (previous * (Decimal(1) - rules.rebaja_threshold)).quantize(Decimal("0.01"))
    rent = _lease(
        contract,
        zona_tensionada=True,
        incumple_lau_17_6=False,
        renta_inicial=exactly_threshold,
        renta_ultima_contrato_anterior=previous,
    )
    early_rehabilitation = _lease(
        contract,
        rehabilitacion_fecha=shift_by_calendar_years(contract, -rules.rehabilitation_lookback_years)
        - timedelta(days=1),
    )
    assert derive_rental_reduction((rent,), devengo=devengo, rules=rules).tier == TIER_50
    assert derive_rental_reduction((early_rehabilitation,), devengo=devengo, rules=rules).tier == TIER_50


def test_a_tensioned_zone_lease_breaching_lau_17_6_and_a_non_dwelling_lease_get_no_reduction(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    breach = _lease(
        rules.contract_cut_off,
        zona_tensionada=True,
        incumple_lau_17_6=True,
        renta_inicial=Decimal("1.00"),
        renta_ultima_contrato_anterior=Decimal("1000.00"),
    )
    not_a_dwelling = _lease(rules.contract_cut_off - timedelta(days=1), uso_vivienda=False)
    for lease in (breach, not_a_dwelling):
        outcome = derive_rental_reduction((lease,), devengo=devengo, rules=rules)
        assert (outcome.aplicable, outcome.tier, outcome.refusal) == (False, None, None)


def test_unstated_deciding_facts_refuse_and_unstated_raising_facts_are_not_claimed(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    contract = rules.contract_cut_off
    refusals = {
        RentalReductionRefusal.USO_VIVIENDA_UNSTATED: _lease(contract, uso_vivienda=None),
        RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED: _lease(contract, zona_tensionada=None),
        RentalReductionRefusal.LAU_17_6_UNSTATED: _lease(contract, zona_tensionada=True),
        RentalReductionRefusal.MIXED_TENANT_AGES: _lease(
            contract,
            zona_tensionada=True,
            incumple_lau_17_6=False,
            primer_arrendamiento_vivienda=True,
            inquilinos=(
                _tenant("X1234567", InquilinoEdad.DE_18_A_35),
                _tenant("Y7654321", InquilinoEdad.OTRA),
            ),
        ),
    }
    for refusal, lease in refusals.items():
        outcome = derive_rental_reduction((lease,), devengo=devengo, rules=rules)
        assert (outcome.aplicable, outcome.tier, outcome.refusal, outcome.lease) == (None, None, refusal, 0)
    unclaimed = _lease(
        contract,
        zona_tensionada=True,
        incumple_lau_17_6=False,
        renta_inicial=Decimal("100.00"),
        primer_arrendamiento_vivienda=None,
        arrendatario_entidad_tipo=ArrendatarioEntidadTipo.ENTIDAD_SIN_FINES_LUCRO,
    )
    assert derive_rental_reduction((unclaimed,), devengo=devengo, rules=rules).tier == TIER_50


def test_no_lease_or_several_leases_in_the_ejercicio_refuse(
    tiered: tuple[RentalReductionArt232Rules, date],
) -> None:
    rules, devengo = tiered
    contract = rules.contract_cut_off
    ended = _lease(contract, fecha_fin=date(devengo.year - 1, 12, 31))
    second = _lease(contract, clave=1)
    assert leases_active_in((ended,), year=devengo.year) == ()
    none = derive_rental_reduction((), devengo=devengo, rules=rules)
    several = derive_rental_reduction(
        leases_active_in((_lease(contract), second), year=devengo.year), devengo=devengo, rules=rules
    )
    assert none.refusal is RentalReductionRefusal.NO_LEASE
    assert several.refusal is RentalReductionRefusal.SEVERAL_LEASES
