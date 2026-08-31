"""Service state of one AEAT electronic notification, as Ley 39/2015 defines it.

A notificación pulled from the DEHu buzón carries two facts about delivery: the
``fecha de notificación`` AEAT stamps when it puts the item at the taxpayer's
disposal, and whether the taxpayer has since accessed the contents. Neither
fact, on its own, answers the question that decides whether the operator must
act: *has this notification already been legally served?*

Ley 39/2015 art. 43.2 answers it. An electronic notification is served at the
moment of access; and where the electronic channel is obligatory or the
interesado chose it, the notification is *deemed rejected* — served in law
despite never having been read — once ten días naturales have elapsed since the
puesta a disposición without access. That deemed service is the rechazo tácito,
and it carries the full consequences of a notification the taxpayer read.

:class:`NotificacionEstadoServicio` is the closed axis of that service state.
It is deliberately ORTHOGONAL to
:class:`~cadrumo.core.PostFilingEventKind`, which closes the *procedural
category* axis (requerimiento, liquidación, providencia de apremio). The two
answer unrelated questions: a requerimiento can independently be accessed,
inside its window, or deemed served, so cross-producting category by state
would multiply enum members combinatorially and make a later "what changed"
diff ambiguous between the two.

The window counts días NATURALES, not hábiles: weekends, holidays and August
all count. A días-hábiles reading computes a later lapse date than the law
allows, which understates urgency to the taxpayer — the wrong direction of
error. The clock runs from the puesta a disposición, never from access.

This module performs no I/O and reads no clock. The evaluation date is an
explicit ``as_of`` argument threaded from the caller, so a projection over a
stored snapshot is reproducible rather than dependent on when it happened to
run.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from .external_constants import DEHU_RECHAZO_TACITO_DIAS_NATURALES


class NotificacionEstadoServicio(StrEnum):
    """Service state of one electronic notification under Ley 39/2015 art. 43.2.

    Attributes:
        NO_ENTREGADA: AEAT has not put the notification at the taxpayer's
            disposal yet, so no ``fecha de notificación`` exists and no window
            has started. The placeholder state for a ``pendiente`` row.
        ACCEDIDA: The taxpayer has accessed the contents. The notification is
            served by access, which is the ordinary path and the one art. 43.2
            names first.
        EN_PLAZO: Put at the taxpayer's disposal and not yet accessed, with
            fewer than ten días naturales elapsed. Still inside the window;
            not yet served.
        RECHAZO_TACITO: Put at the taxpayer's disposal, never accessed, and ten
            or more días naturales elapsed. Deemed rejected and therefore
            legally served — the state that must reach the operator, because
            the taxpayer now bears a notification's consequences without ever
            having read it.
    """

    NO_ENTREGADA = "no_entregada"
    ACCEDIDA = "accedida"
    EN_PLAZO = "en_plazo"
    RECHAZO_TACITO = "rechazo_tacito"


def resolve_notificacion_estado_servicio(
    *,
    fecha_notificacion: date | None,
    leida: bool | None,
    as_of: date,
) -> NotificacionEstadoServicio:
    """Return the art. 43.2 service state of one notification as of ``as_of``.

    Args:
        fecha_notificacion: The puesta a disposición date AEAT stamps on
            delivery, or ``None`` for a row it has not delivered yet.
        leida: Whether AEAT marks the row accessed. ``None`` means the surface
            carried no value, which is treated as not accessed.
        as_of: The date the window is evaluated against. Explicit so a
            projection is reproducible; never defaulted to today.

    Returns:
        The single :class:`NotificacionEstadoServicio` member describing this
        notification's service state.
    """
    if fecha_notificacion is None:
        # No puesta a disposición means no window to run, and nothing to have
        # accessed. This is checked before ``leida`` deliberately: an undelivered
        # row is not served by any reading of art. 43.2, so a stray access flag
        # on a pendiente row must not promote it to ACCEDIDA.
        return NotificacionEstadoServicio.NO_ENTREGADA
    if leida:
        return NotificacionEstadoServicio.ACCEDIDA
    # A negative elapsed count means ``as_of`` precedes the puesta a disposición,
    # so the window has not opened; EN_PLAZO is correct for it.
    elapsed_dias_naturales = (as_of - fecha_notificacion).days
    if elapsed_dias_naturales >= DEHU_RECHAZO_TACITO_DIAS_NATURALES:
        return NotificacionEstadoServicio.RECHAZO_TACITO
    return NotificacionEstadoServicio.EN_PLAZO


__all__ = [
    "NotificacionEstadoServicio",
    "resolve_notificacion_estado_servicio",
]
