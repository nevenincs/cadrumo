"""Modelo 216 has both cadences, so a stated large company gets the monthly one.

Orden EHA/3290/2008 art. 4 declares two plazos for this IRNR retención
autoliquidación, on the authority of RIRNR art. 15.1. Paragraph one puts the
ordinary retenedor on the first twenty natural days of April, July, October and
January; paragraph two moves the declaration to the first twenty natural days of
each month, for the month immediately before, "cuando se trate de retenedores u
obligados que tengan la consideración de grandes empresas por concurrir alguna
de las circunstancias a que se refieren los números 1.º y 2.º del apartado 3 del
artículo 71 del Reglamento del Impuesto sobre el Valor Añadido" -- the volumen
de operaciones that ``enrollment.large_company`` carries. AEAT's own Calendario
del Contribuyente names Modelo 216 in that monthly population every month.

Modelo 216 declared only the quarterly cadence. Once the condition became
three-state, a quarterly schedule needed a stated no, so a taxpayer who stated
that he is a large company selected no schedule at all and the modelo lost every
deadline window: the filer with the stricter obligation was shown none. This is
the same defect Modelos 115 and 123 carried.

Each case resolves the cadence through the real
:func:`applicable_filing_schedules`, the resolver the deadline engine's own
schedule gate calls, over every compiled edition of the modelo. The engine-level
projection of these windows is held by the sibling overview test over the
published authority.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.iva_regime_vocabulary import require_iva_regime
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.calculations.registry.schedules import applicable_filing_schedules
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.contribuyente.entity_type import require_entity_type, require_legal_entity_form
from cadrumo.domain.deadlines.models import ModeloEnrollment, TaxpayerProfile
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_MODELO = "216"
_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_QUARTERS = ("1T", "2T", "3T", "4T")
_MONTHLY_SCHEDULE = "modelo-216-mensual"
_QUARTERLY_SCHEDULE = "modelo-216-trimestral"


def _retenedor(*, answer: bool | None) -> TaxpayerProfile:
    """A legal entity that has answered the large-company condition, or has not."""
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "B00015016",
            "entity_type": require_entity_type("legal_entity"),
            "legal_entity_form": require_legal_entity_form("sl"),
            "iva_regime": require_iva_regime("GENERAL"),
            "enrollment": ModeloEnrollment(large_company=answer),
        },
    )


def _editions() -> tuple[tuple[str, ModeloRevision], ...]:
    """Every compiled edition of the modelo, with its effective members."""
    service = RegistryQueryService(compiled_bundled_authority())
    editions = tuple(
        (revision.id, revision) for _modelo, revision in service.iter_modelo_revisions(modelo_codes=(_MODELO,))
    )
    assert editions, "the compiled registry serves no Modelo 216 edition"
    return editions


def _selected(*, answer: bool | None, period: str) -> dict[str, tuple[str, ...]]:
    """Return, per edition, the ids of the schedules the resolver selects for one period."""
    return {
        revision_id: tuple(
            schedule.id for schedule in applicable_filing_schedules(revision, _retenedor(answer=answer), period=period)
        )
        for revision_id, revision in _editions()
    }


@pytest.mark.parametrize("period", _MONTHS)
def test_a_stated_large_company_is_given_the_monthly_schedule(period: str) -> None:
    """The defect this closes: the stricter filer was given no schedule at all."""
    assert all(ids == (_MONTHLY_SCHEDULE,) for ids in _selected(answer=True, period=period).values()), period


@pytest.mark.parametrize("period", _QUARTERS)
def test_a_stated_ordinary_retenedor_is_given_the_quarterly_schedule(period: str) -> None:
    assert all(ids == (_QUARTERLY_SCHEDULE,) for ids in _selected(answer=False, period=period).values()), period


@pytest.mark.parametrize("period", (*_MONTHS, *_QUARTERS))
def test_an_unanswered_condition_is_given_neither_cadence(period: str) -> None:
    """Neither cadence may be guessed: adding the monthly schedule revives no default."""
    assert all(ids == () for ids in _selected(answer=None, period=period).values()), period


@pytest.mark.parametrize("period", _MONTHS)
def test_the_monthly_period_never_selects_the_quarterly_schedule(period: str) -> None:
    """A filer is on one cadence or the other, never on a mixture of the two."""
    for answer in (True, False):
        for revision_id, ids in _selected(answer=answer, period=period).items():
            assert _QUARTERLY_SCHEDULE not in ids, (revision_id, answer, period)


def test_every_edition_declares_both_cadences_over_the_whole_year() -> None:
    for revision_id, revision in _editions():
        by_id = {schedule.id: schedule for schedule in revision.filing_schedules}
        assert set(by_id) == {_MONTHLY_SCHEDULE, _QUARTERLY_SCHEDULE}, revision_id
        assert tuple(sorted(by_id[_MONTHLY_SCHEDULE].periods)) == _MONTHS, revision_id
        assert tuple(sorted(by_id[_QUARTERLY_SCHEDULE].periods)) == _QUARTERS, revision_id


def test_every_monthly_coordinate_in_the_support_envelope_owns_a_window() -> None:
    """The years come from the registry's own envelope, never a list of their own."""
    authority = compiled_bundled_authority()
    support = authority.supported_filing_years()
    authored = {
        (window.period.filing_year, window.period.code)
        for _revision_id, revision in _editions()
        for window in revision.deadline_windows
        if window.period_kind == "monthly"
    }

    expected = {(year, month) for year in support.years for month in _MONTHS}

    assert expected
    assert authored == expected


def test_each_monthly_window_closes_in_the_month_after_its_own_period() -> None:
    """The closes are the published ones, so each opens after its period ends."""
    seen = 0
    for revision_id, revision in _editions():
        for window in revision.deadline_windows:
            if window.period_kind != "monthly":
                continue
            seen += 1
            year, month = window.period.filing_year, int(window.period.code)
            after = (year + 1, 1) if month == 12 else (year, month + 1)
            assert (window.opens_on.year, window.opens_on.month) == after, (revision_id, window.id)
            assert window.opens_on.day == 1, (revision_id, window.id)
            assert (window.closes_on.year, window.closes_on.month) == after, (revision_id, window.id)
            assert window.closes_on >= window.opens_on, (revision_id, window.id)
    assert seen == len(_MONTHS) * len(compiled_bundled_authority().supported_filing_years().years)
