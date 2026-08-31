"""Boundary contract for the Ley 39/2015 art. 43.2 rechazo-tacito window.

These are structural boundary tests, not value-from-formula tests: the only
number they encode is the ten-dias-naturales figure the statute states, and
every assertion is about WHICH state the window arithmetic selects on either
side of that boundary. The figure itself is grounded in the bundled corpus
excerpt and the pinned leaf constant, not re-derived here.

See Also:
    :mod:`~core.notificacion_estado_servicio`
        Module under test.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ... import core as core_facade
from ..notificacion_estado_servicio import NotificacionEstadoServicio, resolve_notificacion_estado_servicio
from ..external_constants import DEHU_RECHAZO_TACITO_DIAS_NATURALES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PUESTA_A_DISPOSICION = date(2026, 3, 2)
"""An arbitrary delivery date. Deliberately spans a weekend in every window
below, so a dias-habiles implementation would disagree with these expectations."""


def _estado(*, elapsed_days: int, leida: bool | None = False) -> NotificacionEstadoServicio:
    return resolve_notificacion_estado_servicio(
        fecha_notificacion=PUESTA_A_DISPOSICION,
        leida=leida,
        as_of=PUESTA_A_DISPOSICION + timedelta(days=elapsed_days),
    )


def test_day_nine_is_still_inside_the_window() -> None:
    """Nine dias naturales elapsed: art. 43.2's ten have not, so not yet served."""
    assert _estado(elapsed_days=9) is NotificacionEstadoServicio.EN_PLAZO


def test_day_ten_is_deemed_rejected() -> None:
    """Ten dias naturales elapsed without access is the rechazo tacito the statute fixes."""
    assert _estado(elapsed_days=10) is NotificacionEstadoServicio.RECHAZO_TACITO


def test_the_deemed_rejected_state_persists_past_the_boundary() -> None:
    """The state does not revert once the window has lapsed."""
    assert _estado(elapsed_days=400) is NotificacionEstadoServicio.RECHAZO_TACITO


def test_day_zero_is_inside_the_window() -> None:
    """The puesta a disposicion day itself starts the window rather than ending it."""
    assert _estado(elapsed_days=0) is NotificacionEstadoServicio.EN_PLAZO


def test_an_undelivered_row_has_no_window() -> None:
    """No fecha de notificacion means AEAT has not put the item at the taxpayer's disposal."""
    assert (
        resolve_notificacion_estado_servicio(
            fecha_notificacion=None,
            leida=False,
            as_of=PUESTA_A_DISPOSICION,
        )
        is NotificacionEstadoServicio.NO_ENTREGADA
    )


def test_an_undelivered_row_is_not_promoted_by_a_stray_access_flag() -> None:
    """An undelivered row is served under no reading of art. 43.2.

    The ordering of the two guards is load-bearing, not incidental: checking
    ``leida`` first would let a pendiente row carrying a stray access flag
    report ACCEDIDA, asserting service on an item never delivered.
    """
    assert (
        resolve_notificacion_estado_servicio(
            fecha_notificacion=None,
            leida=True,
            as_of=PUESTA_A_DISPOSICION,
        )
        is NotificacionEstadoServicio.NO_ENTREGADA
    )


@pytest.mark.parametrize("elapsed_days", [0, 9, 10, 400])
def test_access_serves_the_notification_regardless_of_elapsed_days(elapsed_days: int) -> None:
    """Access is the ordinary service path art. 43.2 names first.

    Once accessed, the window is spent on both sides of the boundary: a
    notification read on day 400 is ACCEDIDA, never RECHAZO_TACITO, because
    deemed rejection is defined by the ABSENCE of access.
    """
    assert _estado(elapsed_days=elapsed_days, leida=True) is NotificacionEstadoServicio.ACCEDIDA


@pytest.mark.parametrize("elapsed_days", [9, 10])
def test_a_missing_access_value_is_treated_as_not_accessed(elapsed_days: int) -> None:
    """A pendiente-shaped ``None`` must not be read as access.

    Treating an absent value as accessed would silently suppress the very state
    the operator needs, so the absent case follows the not-accessed branch and
    the window still governs.
    """
    assert _estado(elapsed_days=elapsed_days, leida=None) == _estado(elapsed_days=elapsed_days, leida=False)


def test_an_as_of_before_delivery_has_not_opened_the_window() -> None:
    """A negative elapsed count is inside the window, never past it."""
    assert _estado(elapsed_days=-5) is NotificacionEstadoServicio.EN_PLAZO


def test_the_boundary_is_the_pinned_statutory_constant() -> None:
    """The window boundary is the pinned constant, not a literal in the function.

    Anchors the boundary tests above to the grounded constant: if the constant
    were re-pinned, the day-9 / day-10 expectations would be measuring a
    different rule than the one production reads.
    """
    assert DEHU_RECHAZO_TACITO_DIAS_NATURALES == 10
    assert _estado(elapsed_days=DEHU_RECHAZO_TACITO_DIAS_NATURALES - 1) is NotificacionEstadoServicio.EN_PLAZO
    assert _estado(elapsed_days=DEHU_RECHAZO_TACITO_DIAS_NATURALES) is NotificacionEstadoServicio.RECHAZO_TACITO


def test_the_day_ten_assertion_discriminates_against_an_off_by_one_boundary() -> None:
    """Anti-tautology proof: the day-10 expectation is not satisfiable by both readings.

    The plausible defect here is an off-by-one on the comparison -- ``elapsed >
    10`` where art. 43.2 requires ``elapsed >= 10`` -- which defers deemed
    service by a day and understates urgency. This proves the day-10 assertion
    above can tell the two apart, so it is load-bearing rather than a boundary
    both implementations satisfy.

    It also proves the discrimination is specific: at day 11 the two readings
    agree, so day 10 is the only elapsed count where the defect is observable
    and the boundary test is aimed at exactly the right day.
    """

    def off_by_one_reading(elapsed_days: int) -> NotificacionEstadoServicio:
        if elapsed_days > DEHU_RECHAZO_TACITO_DIAS_NATURALES:
            return NotificacionEstadoServicio.RECHAZO_TACITO
        return NotificacionEstadoServicio.EN_PLAZO

    at_boundary = DEHU_RECHAZO_TACITO_DIAS_NATURALES
    assert _estado(elapsed_days=at_boundary) is not off_by_one_reading(at_boundary)
    assert _estado(elapsed_days=at_boundary - 1) is off_by_one_reading(at_boundary - 1)
    assert _estado(elapsed_days=at_boundary + 1) is off_by_one_reading(at_boundary + 1)


def test_the_axis_is_reachable_through_the_core_facade() -> None:
    """Consumers outside ``core`` resolve both symbols through the package facade."""
    assert core_facade.NotificacionEstadoServicio is NotificacionEstadoServicio
    assert core_facade.resolve_notificacion_estado_servicio is resolve_notificacion_estado_servicio
    assert "NotificacionEstadoServicio" in core_facade.__all__
    assert "resolve_notificacion_estado_servicio" in core_facade.__all__
