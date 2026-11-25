"""The Art. 81.1 post-birth alta increment, resolved through the real production path.

``resolve_maternidad_meses`` is what the calculate path actually calls
(:func:`~cadrumo.application.modelo.calculate_input.apply_calculation_shortcut_inputs`
consumes it via ``_resolved_maternidad_meses``). These tests drive it directly
against the resident registry authority and a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` -- no mocks, no
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

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.contribuyente.deduccion_maternidad import compute_deduccion_maternidad_0611
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_maternidad_meses import resolve_maternidad_meses

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

# The exercise of the AEAT Manual practico de Renta worked example this module
# reproduces: the earliest edition that prints it, which is also the first exercise
# the alta-posterior increment applies to.
_MANUAL_EXERCISE = min(
    manual_editions_printing("renta", "alta en la seguridad social con posterioridad al nacimiento y 30 dias cotizados")
)

_BUCKET = "0de41ce4-0000-4000-8000-000000000611"
_T0 = datetime(_MANUAL_EXERCISE + 3, 8, 5, 10, 0, tzinfo=UTC)

#: Both mellizos: born January 2023, alta completed in May 2023 -- eight
#: qualifying months (May-December).
_MELLIZO_BIRTH = date(_MANUAL_EXERCISE, 1, 15)


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _record(*descendientes: DescendantInfo) -> UserProfileRecord:
    facts = tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes))
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _mellizo(meses: tuple[int, ...], *, alta_mes: int | None) -> DescendantInfo:
    return DescendantInfo(
        birth_date=_MELLIZO_BIRTH,
        meses_madre_trabajo=meses,
        alta_posterior_nacimiento_mes=alta_mes,
    )


def test_a_declared_completion_month_is_carried_for_the_manual_exercise() -> None:
    """The resolved ``alta_posterior_hijos`` set names the declared child in the manual exercise."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        record = _record(_mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5))

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE), operation=_authority_operation_for_test
        )

        assert resolution.pairs == (("0", 8),)
        assert resolution.alta_posterior_hijos == frozenset({"0"})


def test_the_manual_worked_example_reproduces_through_the_real_resolver() -> None:
    """Two mellizos, oracle-anchored: 950 each, 1.900 together, through the real path."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        record = _record(
            _mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5), _mellizo((5, 6, 7, 8, 9, 10, 11, 12), alta_mes=5)
        )

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE), operation=_authority_operation_for_test
        )
        deduccion = compute_deduccion_maternidad_0611(
            list(resolution.pairs),
            filing_year=_MANUAL_EXERCISE,
            alta_posterior_hijos=resolution.alta_posterior_hijos,
        )

        assert deduccion == 1900


def test_the_older_hijo_mayor_figure_reproduces_through_the_real_resolver() -> None:
    """The manual's older-child line, isolated: four months, one increment, 550."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        older_hijo = DescendantInfo(
            birth_date=date(_MANUAL_EXERCISE - 3, 9, 2),
            meses_madre_trabajo=(5, 6, 7, 8),
            alta_posterior_nacimiento_mes=5,
        )
        record = _record(older_hijo)

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE), operation=_authority_operation_for_test
        )
        deduccion = compute_deduccion_maternidad_0611(
            list(resolution.pairs),
            filing_year=_MANUAL_EXERCISE,
            alta_posterior_hijos=resolution.alta_posterior_hijos,
        )

        assert deduccion == 550


def test_the_same_declared_profile_carries_no_increment_one_filing_year_earlier() -> None:
    """The edition boundary, proven both ways: the manual exercise grants it, the year before does not.

    The SAME descendant, the SAME declared completion month, one filing year
    earlier. ``alta_posterior_hijos`` must be empty, which is the boundary this
    module exists to prove: the post-birth alta route did not reach a mother
    before the reform. The months still contribute, so ``pairs`` is not empty and
    the plain computation yields the ordinary 800.

    That edition also limits each child by the mother's cotizaciones, and this
    child states no figure, so the resolution reports the figure as missing and
    the limited computation leaves the deducción unresolved rather than granting
    the ordinary amount.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        child = DescendantInfo(
            birth_date=date(_MANUAL_EXERCISE - 2, 6, 1),
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        record = _record(child)

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE - 1), operation=_authority_operation_for_test
        )

        assert resolution.alta_posterior_hijos == frozenset()
        assert resolution.pairs == (("0", 8),)
        assert resolution.cotizaciones_limit_applies is True
        assert resolution.cotizaciones_figure_missing is True

        assert (
            compute_deduccion_maternidad_0611(
                list(resolution.pairs),
                filing_year=_MANUAL_EXERCISE - 1,
                alta_posterior_hijos=resolution.alta_posterior_hijos,
            )
            == 800
        )


def test_a_child_with_no_declared_completion_month_is_never_in_the_increment_set() -> None:
    """The ordinary case: no month declared, no increment, regardless of filing year."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        record = _record(_mellizo((1, 2, 3, 4, 5, 6, 7, 8), alta_mes=None))

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE), operation=_authority_operation_for_test
        )

        assert resolution.alta_posterior_hijos == frozenset()


def test_an_ineligible_child_is_never_in_the_increment_set_even_with_a_declared_month() -> None:
    """A withheld pair must never surface in the increment set.

    A non-cohabiting child contributes zero months to ``pairs`` (the ordinary
    Art. 81.1 eligibility gate), so even though it declares a completion month,
    the increment can never reach a descendant the ordinary predicate excludes.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        non_cohabiting = DescendantInfo(
            birth_date=_MELLIZO_BIRTH,
            convive_con_contribuyente=False,
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        record = _record(non_cohabiting)

        resolution = resolve_maternidad_meses(
            record, _snapshot(_MANUAL_EXERCISE), operation=_authority_operation_for_test
        )

        assert resolution.pairs == ()
        assert resolution.alta_posterior_hijos == frozenset()
