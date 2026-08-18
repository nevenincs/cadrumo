"""The Art. 81.1 post-birth alta increment, resolved through the real production path.

``resolve_maternidad_meses`` is what the calculate path actually calls
(:func:`~cadrumo.application.modelo._calculate_input.apply_calculation_shortcut_inputs`
consumes it via ``_resolved_maternidad_meses``). These tests drive it directly
against the resident registry authority and a real
:class:`~cadrumo.domain.user_profile.UserProfileRecord` -- no mocks, no
monkeypatched engine -- and feed its output straight into
:func:`~cadrumo.domain.contribuyente.compute_deduccion_maternidad_0611`, the
same function the calculate path calls, so the whole resolution chain is
proven rather than only the arithmetic in isolation.

Oracle anchoring: the AEAT Manual Práctico de Renta 2023 worked example ("Alta
en la Seguridad Social con posterioridad al nacimiento y 30 días cotizados en
el mes de mayo") -- mellizos at 8 qualifying months each, 950 euros per
mellizo, 1.900 total. Filing year 2022, one year earlier with the identical
profile, must resolve to no increment at all: the year boundary this module
exists to prove. For 2022 it resolves to no DEDUCCIÓN at all, which is a
second and independent pre-2023 rule -- the cotizaciones ceiling, unreachable
for those years -- rather than a stronger form of this one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshot
from ....domain.contribuyente import (
    DescendantInfo,
    compute_deduccion_maternidad_0611,
    descendant_facts_from_list,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._profile_binding import resolve_maternidad_meses

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000611"
_T0 = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)

#: Both mellizos: born January 2023, alta completed in May 2023 -- eight
#: qualifying months (May-December).
_MELLIZO_BIRTH = date(2023, 1, 15)


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=year, period="0A")


def _record(*descendientes: DescendantInfo) -> UserProfileRecord:
    facts = tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes))
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
    )


def _mellizo(meses: tuple[int, ...], *, alta_mes: int | None) -> DescendantInfo:
    return DescendantInfo(
        birth_date=_MELLIZO_BIRTH,
        meses_madre_trabajo=meses,
        alta_posterior_nacimiento_mes=alta_mes,
    )


def test_a_declared_completion_month_is_carried_for_2023() -> None:
    """The resolved ``alta_posterior_hijos`` set names the declared child in 2023."""
    record = _record(_mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5))

    resolution = resolve_maternidad_meses(record, _snapshot(2023))

    assert resolution.pairs == (("0", 8),)
    assert resolution.alta_posterior_hijos == frozenset({"0"})


def test_the_manual_worked_example_reproduces_through_the_real_resolver() -> None:
    """Two mellizos, oracle-anchored: 950 each, 1.900 together, through the real path."""
    record = _record(
        _mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5), _mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5)
    )

    resolution = resolve_maternidad_meses(record, _snapshot(2023))
    deduccion = compute_deduccion_maternidad_0611(
        list(resolution.pairs),
        filing_year=2023,
        alta_posterior_hijos=resolution.alta_posterior_hijos,
    )

    assert deduccion == 1900


def test_the_older_hijo_mayor_figure_reproduces_through_the_real_resolver() -> None:
    """The manual's older-child line, isolated: four months, one increment, 550."""
    older_hijo = DescendantInfo(
        birth_date=date(2020, 9, 2),
        meses_madre_trabajo=(5, 6, 7, 8),
        alta_posterior_nacimiento_mes=5,
    )
    record = _record(older_hijo)

    resolution = resolve_maternidad_meses(record, _snapshot(2023))
    deduccion = compute_deduccion_maternidad_0611(
        list(resolution.pairs),
        filing_year=2023,
        alta_posterior_hijos=resolution.alta_posterior_hijos,
    )

    assert deduccion == 550


def test_the_same_declared_profile_carries_no_increment_one_filing_year_earlier() -> None:
    """The year boundary, proven both ways: 2023 grants it (above), 2022 grants nothing.

    The SAME descendant, the SAME declared completion month, one filing year
    earlier. ``alta_posterior_hijos`` must be empty, which is the boundary this
    module exists to prove: the post-birth alta route did not reach a mother
    before 2023.

    The deducción is 0 rather than the ordinary 800, and the reason is a SECOND,
    independent pre-2023 rule rather than this one. Until 2022 Art. 81.1 was
    still capped at the mother's cotizaciones devengadas in the period, and this
    application holds no cotizaciones figure for those years, so the resolver
    withholds the whole deducción rather than granting it un-capped
    (``cotizaciones_ceiling_inexpressible``). ``pairs`` is therefore empty too.

    Do not "restore" the 800 by asserting the ordinary months still contribute.
    That figure is exactly the un-ceilinged over-grant the cotizaciones gate
    removed, and asserting it here would reinstate it behind a green test. The
    per-year sweep of that withholding is owned by
    ``test_maternidad_cotizaciones_ceiling``; this test only pins that the alta
    increment cannot arrive through it.
    """
    child = DescendantInfo(
        birth_date=date(2021, 6, 1),
        meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
        alta_posterior_nacimiento_mes=5,
    )
    record = _record(child)

    resolution = resolve_maternidad_meses(record, _snapshot(2022))

    assert resolution.alta_posterior_hijos == frozenset()
    assert resolution.pairs == ()
    assert resolution.cotizaciones_ceiling_inexpressible is True

    deduccion = compute_deduccion_maternidad_0611(
        list(resolution.pairs),
        filing_year=2022,
        alta_posterior_hijos=resolution.alta_posterior_hijos,
    )
    assert deduccion == 0


def test_a_child_with_no_declared_completion_month_is_never_in_the_increment_set() -> None:
    """The ordinary case: no month declared, no increment, regardless of filing year."""
    record = _record(_mellizo((1, 2, 3, 4, 5, 6, 7, 8), alta_mes=None))

    resolution = resolve_maternidad_meses(record, _snapshot(2023))

    assert resolution.alta_posterior_hijos == frozenset()


def test_an_ineligible_child_is_never_in_the_increment_set_even_with_a_declared_month() -> None:
    """A withheld pair must never surface in the increment set.

    A non-cohabiting child contributes zero months to ``pairs`` (the ordinary
    Art. 81.1 eligibility gate), so even though it declares a completion month,
    the increment can never reach a descendant the ordinary predicate excludes.
    """
    non_cohabiting = DescendantInfo(
        birth_date=_MELLIZO_BIRTH,
        convive_con_contribuyente=False,
        meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
        alta_posterior_nacimiento_mes=5,
    )
    record = _record(non_cohabiting)

    resolution = resolve_maternidad_meses(record, _snapshot(2023))

    assert resolution.pairs == ()
    assert resolution.alta_posterior_hijos == frozenset()
