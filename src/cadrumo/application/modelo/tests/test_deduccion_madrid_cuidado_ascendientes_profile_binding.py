"""The Madrid deducción por cuidado de ascendientes, from stored rows through the real resolver.

DL 1/2010 art. 7 bis (Comunidad de Madrid) grants 515,50 euros for each ascendant
over 65, or with a disability of at least 33 per cent, for whom the filer applies
the mínimo por ascendientes, shared in equal parts when the ascendant entitles more
than one filer. The article sets no income limit. The Manual práctico de Renta
prints it in the Madrid deducciones of the editions that carry it; whether an
edition carries it is read here from that text, not from the registry, so a box
declared in the wrong edition fails the test.

Every supported year is enumerated from the registry's support envelope. A year
without its own edition reads the edition it is projected from.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.formula_expression import evaluate_expression
from ....domain.calculations.registry.formula_runtime_ops import UnresolvedFormulaDependencyError, apply_rounding
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, manual_editions_printing
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...aggregation.source_mesh import CalculationSourceResolution
from ..autonomic_deduccion_dispatch import AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000001115"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)
_ROLE = "irpf_deduccion_madrid_cuidado_ascendientes"
_BINDING = "renta-profile-deduccion-madrid-cuidado-ascendientes-count"
_GROUP = "renta_family.ascendiente"

# DL 1/2010 art. 7 bis, as each manual edition that carries it prints it.
_AMOUNT = Decimal("515.50")
_ARTICLE_TEXT = "515,50 euros por cada ascendiente mayor de 65 años o con discapacidad igual o"
_EDITIONS_WITH_THE_DEDUCCION = manual_editions_printing("renta", _ARTICLE_TEXT)

_YEARS = filing_year_envelope().years


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _carries_the_deduccion(year: int) -> bool:
    snapshot = _snapshot(year)
    return (snapshot.authored_filing_year or year) in _EDITIONS_WITH_THE_DEDUCCION


def _box(snapshot: RegistrySnapshot) -> str | None:
    matches = [casilla.id for casilla in snapshot.revision.casillas if casilla.semantic_role == _ROLE]
    assert len(matches) <= 1
    return matches[0] if matches else None


def _born(year: int, age: int) -> date:
    """A birth date that gives ``age`` full years at 31 December of ``year``."""
    return date(year - age, 6, 1)


def _record(ccaa: str | None, *rows: dict[str, str]) -> UserProfileRecord:
    facts = [UserProfileFact(path="renta_family.ascendientes_count", value=str(len(rows)))]
    if ccaa is not None:
        facts.append(UserProfileFact(path="tax_residence.ccaa", value=ccaa))
    for index, row in enumerate(rows):
        facts.extend(UserProfileFact(path=f"{_GROUP}.{index}.{leaf}", value=value) for leaf, value in row.items())
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(facts),
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _resolve(year: int, record: UserProfileRecord, operation: PinnedAuthorityOperation) -> CalculationSourceResolution:
    return resolve_profile_sourced_bindings(
        _snapshot(year), bucket_id=_BUCKET, profile_record=record, operation=operation
    )


def _casilla(year: int, casilla_id: str, resolution: CalculationSourceResolution) -> Decimal | None:
    """Evaluate the edition's formula for ``casilla_id``, or ``None`` when it cannot settle."""
    snapshot = _snapshot(year)
    (formula,) = (formula for formula in snapshot.revision.formulas if formula.target_casilla_id == casilla_id)
    try:
        value = evaluate_expression(
            formula.expression,
            values={},
            binding_values=resolution.binding_values,
            parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
            date_context={"filing_period": date(year, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
            unresolved_binding_ids=frozenset(resolution.unresolved_binding_ids),
            filing_year=snapshot.filing_year,
        )
    except UnresolvedFormulaDependencyError:
        return None
    return apply_rounding(value, formula.rounding)


def _mother(year: int, age: int = 78, **changes: str | None) -> dict[str, str]:
    """The asalariada-familia ascendant: living with the filer alone, below the ceilings."""
    row: dict[str, str | None] = {
        "birth_date": _born(year, age).isoformat(),
        "convivientes": "1",
        "rentas_anuales": "7200.00",
        "declaracion_propia": "false",
        **changes,
    }
    return {leaf: value for leaf, value in row.items() if value is not None}


def _limitations(resolution: CalculationSourceResolution) -> list[str]:
    return [
        diagnostic.reason
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON
    ]


def test_the_manuals_carry_the_deduccion_in_some_supported_editions_and_not_in_others() -> None:
    """The oracle distinguishes both cases, so every year below exercises one of them."""
    carried = {_carries_the_deduccion(year) for year in _YEARS}

    assert carried == {True, False}


@pytest.mark.parametrize("year", _YEARS)
def test_a_madrid_resident_caring_for_an_entitled_ascendant_reaches_the_box_where_the_edition_carries_it(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    resolution = _resolve(year, _record("madrid", _mother(year)), authority_operation)
    box = _box(_snapshot(year))

    if not _carries_the_deduccion(year):
        assert box is None
        assert _BINDING not in resolution.binding_values
        # Madrid enrols nothing in that edition, so its resident is told the regional deducciones are by hand.
        assert _limitations(resolution) == [AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON]
        return
    assert box is not None
    assert resolution.binding_values[_BINDING] == Decimal("1")
    assert _BINDING not in resolution.unresolved_binding_ids
    assert _casilla(year, box, resolution) == _AMOUNT
    assert _limitations(resolution) == []


@pytest.mark.parametrize("year", _YEARS)
def test_an_unstated_deciding_fact_refuses_the_box_with_the_ascendant_door(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    """Under 65 the grade decides both the mínimo and the deducción; unstated, it is owed."""
    resolution = _resolve(year, _record("madrid", _mother(year, age=60)), authority_operation)
    box = _box(_snapshot(year))

    discapacidad_ref = f"profile:{_BUCKET}:rows:{_GROUP}.discapacidad"
    owed = [
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "household_row_fact_unstated" and diagnostic.source_ref == discapacidad_ref
    ]
    # One note for the leaf: the mínimo and the deducción owe the same fact of the same row.
    assert len(owed) == 1
    assert owed[0].fact is not None
    if box is None:
        assert not _carries_the_deduccion(year)
        return
    assert _BINDING not in resolution.binding_values
    assert _BINDING in resolution.unresolved_binding_ids
    assert _casilla(year, box, resolution) is None


@pytest.mark.parametrize("year", [year for year in _YEARS if _carries_the_deduccion(year)])
def test_stated_facts_that_rule_the_deduccion_out_give_a_proven_zero(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    box = _box(_snapshot(year))
    assert box is not None
    ruled_out = (
        _mother(year, age=60, discapacidad="0"),
        _mother(year, convivientes="0", rentas_anuales=None),
        _mother(year, rentas_anuales="9000.00", convivientes=None),
    )

    for row in ruled_out:
        resolution = _resolve(year, _record("madrid", row), authority_operation)

        assert resolution.binding_values[_BINDING] == Decimal("0"), row
        assert _BINDING not in resolution.unresolved_binding_ids, row
        assert _casilla(year, box, resolution) == Decimal("0"), row


@pytest.mark.parametrize("year", [year for year in _YEARS if _carries_the_deduccion(year)])
def test_a_disabled_ascendant_under_65_qualifies_and_the_amount_is_shared_as_the_minimum_is(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    box = _box(_snapshot(year))
    assert box is not None
    rows = (
        _mother(year, age=60, discapacidad="33"),
        _mother(year, age=80, convivientes="2"),
    )

    resolution = _resolve(year, _record("madrid", *rows), authority_operation)

    assert _casilla(year, box, resolution) == _AMOUNT + _AMOUNT / 2


@pytest.mark.parametrize("ccaa", ["cataluna", None])
@pytest.mark.parametrize("year", _YEARS)
def test_a_filer_outside_madrid_gets_a_zero_box_and_the_served_limitation(
    year: int, ccaa: str | None, authority_operation: PinnedAuthorityOperation
) -> None:
    """Neither Cataluña nor an unstated comunidad has an enrolment, so the limitation is served."""
    resolution = _resolve(year, _record(ccaa, _mother(year)), authority_operation)
    box = _box(_snapshot(year))

    assert _limitations(resolution) == [AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON]
    if box is not None:
        assert resolution.binding_values[_BINDING] == Decimal("0")
        assert _casilla(year, box, resolution) == Decimal("0")
