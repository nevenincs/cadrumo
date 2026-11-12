"""Casilla 0611 under the cotizaciones limit art. 81.1 LIRPF set until the Ley 31/2022 reform.

The Manual Practico de Renta 2022 (cap. 18, "Cuantia y limite de la deduccion")
gives 100 euros for each month in which the requirements hold together and bars
a deduccion above 1.200 euros a year or above the cotizaciones y cuotas totales a
la Seguridad Social y Mutualidades devengadas after the child's birth, for each
child. The later manuals drop the second bound.

Each edition states which rule it follows by the profile selector its 0611
binding consumes; nothing in the code decides from a year. The oracle for which
editions carry the limit is the corpus itself: the manuals that print the limit
sentence. Every expected euro figure below is worked by hand from the 100 euros a
month and the 1.200 euros cap, not read back from the resolver.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....domain.calculations.registry.profile_bindings import ProfileProvider
from ....domain.calculations.registry.runtime_graph import expression_binding_refs
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import manual_editions_printing
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000000626"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)

#: The manuals that print the sentence bounding each child's deduccion by the cotizaciones.
_LIMIT_SENTENCE = "no podrá superar ninguna de las dos cantidades"
_LIMITED_EDITIONS = frozenset(manual_editions_printing("renta", _LIMIT_SENTENCE))


def _supported_years() -> tuple[int, ...]:
    supported_years = published_supported_filing_years()
    assert supported_years is not None, "the bundled registry declares no supported filing years"
    return supported_years.years


_YEARS = _supported_years()


def _child(filing_year: int, *, meses: tuple[int, ...], cotizaciones: Decimal | None) -> DescendantInfo:
    return DescendantInfo(
        birth_date=date(filing_year - 1, 1, 15),
        meses_madre_trabajo=meses,
        cotizaciones_ss_madre_euros=cotizaciones,
    )


def _record(*children: DescendantInfo) -> UserProfileRecord:
    facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        *(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(children)),
    )
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _snapshot(filing_year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=filing_year, period="0A")


def _binding_id_of_0611(snapshot: RegistrySnapshot) -> str:
    """The binding the edition's own formula for casilla 0611 reads, followed from the registry."""
    casilla = next(c for c in snapshot.revision.casillas if str(c.id) == "0611")
    assert casilla.formula is not None
    formula = next(f for f in snapshot.revision.formulas if f.id == casilla.formula)
    (binding_id,) = expression_binding_refs(formula.expression)
    return str(binding_id)


def _casilla_0611(
    filing_year: int, record: UserProfileRecord, *, operation: PinnedAuthorityOperation
) -> Decimal | None:
    """Casilla 0611 as the edition's formula leaf and the real profile resolver produce it."""
    snapshot = _snapshot(filing_year)
    resolved = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET, profile_record=record, operation=operation)
    values = {str(key): value for key, value in resolved.binding_values.items()}
    return values.get(_binding_id_of_0611(snapshot))


def _limited(filing_year: int) -> bool:
    return filing_year in _LIMITED_EDITIONS


def test_the_envelope_carries_both_rules() -> None:
    """The sweep below is only meaningful if the envelope has limited and unlimited editions."""
    assert any(_limited(year) for year in _YEARS)
    assert any(not _limited(year) for year in _YEARS)


@pytest.mark.parametrize("filing_year", _YEARS)
def test_the_edition_binding_follows_the_rule_its_manual_prints(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    binding = next(b for b in snapshot.revision.bindings if str(b.id) == _binding_id_of_0611(snapshot))
    assert isinstance(binding.provider, ProfileProvider), filing_year
    assert binding.provider.profile_key is not None, filing_year
    assert binding.provider.profile_key.endswith("_cotizaciones") is _limited(filing_year), filing_year


@pytest.mark.parametrize("filing_year", _YEARS)
def test_a_whole_year_of_activity_is_capped_at_1200_or_by_the_cotizaciones(
    filing_year: int, *, operation: PinnedAuthorityOperation
) -> None:
    """Twelve months at 100 euros reach the 1.200 cap; a smaller figure binds only where the edition limits."""
    months = tuple(range(1, 13))
    ample = _casilla_0611(
        filing_year, _record(_child(filing_year, meses=months, cotizaciones=Decimal("5000"))), operation=operation
    )
    assert ample == Decimal("1200"), filing_year

    scant = _casilla_0611(
        filing_year, _record(_child(filing_year, meses=months, cotizaciones=Decimal("500.50"))), operation=operation
    )
    assert scant == (Decimal("500.50") if _limited(filing_year) else Decimal("1200")), filing_year


@pytest.mark.parametrize("filing_year", _YEARS)
def test_each_child_is_limited_by_its_own_cotizaciones(
    filing_year: int, *, operation: PinnedAuthorityOperation
) -> None:
    """Six months is 600 and nine months 900; the limit applies per child, never to their sum."""
    record = _record(
        _child(filing_year, meses=tuple(range(1, 7)), cotizaciones=Decimal("400")),
        _child(filing_year, meses=tuple(range(1, 10)), cotizaciones=Decimal("5000")),
    )
    assert _casilla_0611(filing_year, record, operation=operation) == (
        Decimal("1300") if _limited(filing_year) else Decimal("1500")
    ), filing_year


@pytest.mark.parametrize("filing_year", _YEARS)
def test_a_missing_cotizaciones_figure_leaves_the_box_unresolved_only_where_the_edition_limits(
    filing_year: int, *, operation: PinnedAuthorityOperation
) -> None:
    value = _casilla_0611(
        filing_year,
        _record(_child(filing_year, meses=tuple(range(1, 5)), cotizaciones=None)),
        operation=operation,
    )
    assert value == (None if _limited(filing_year) else Decimal("400")), filing_year


@pytest.mark.parametrize("filing_year", _YEARS)
def test_no_months_is_a_resolved_zero_not_an_unresolved_box(
    filing_year: int, *, operation: PinnedAuthorityOperation
) -> None:
    """A child contributing no months needs no figure, so the sum is a genuine zero."""
    value = _casilla_0611(
        filing_year,
        _record(_child(filing_year, meses=(), cotizaciones=None)),
        operation=operation,
    )
    assert value == Decimal("0"), filing_year
