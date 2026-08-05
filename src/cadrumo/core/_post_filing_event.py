"""Closed taxonomy of AEAT post-filing event categories.

After a taxpayer files, AEAT produces a stream of post-filing events that
the application pulls read-only from two sede surfaces: the
notifications/communications inbox (``RemoteNotification``) and the
declaration register / expedientes (``Declaracion``), plus the local
justificante capture that acknowledges a filing. Those surfaces carry only
a coarse row class (a notification is ``notificacion`` / ``comunicacion`` /
``pendiente``; an expediente is a filed declaration), which erases the
*procedural category* that decides whether the operator must act.

:class:`PostFilingEventKind` is the single closed axis of the real AEAT
post-filing procedural categories — the concepts an operator recognises on
the sede: a ``requerimiento`` demanding documents within a deadline, a
``propuesta de liquidación`` from a comprobación, a ``diligencia de
embargo`` or ``providencia de apremio`` from recaudación, a ``resolución``,
an ``acuerdo de inicio de procedimiento sancionador``, and so on. Declaring
the axis in ``core`` per the core-authority discipline (closed value sets
live in ``core/`` as a :class:`enum.StrEnum`, hydrated at boundaries and
asserted as members in tests) lets every read surface classify a pulled
event into one category and lets the overview flag the actionable ones.

The taxonomy is grounded in the standard AEAT trámite categories published
on the sede electrónica; it is a read-only classification and never drives
any live write.
"""

from __future__ import annotations

from enum import StrEnum

from .text_fold import fold_diacritics


def _fold(text: str) -> str:
    """Lowercase and strip diacritics so substring matching is accent-insensitive."""
    return fold_diacritics(text).casefold().strip()


class PostFilingEventKind(StrEnum):
    """Procedural category of one AEAT post-filing event.

    The members span the categories AEAT actually emits after a filing,
    ordered loosely from acknowledgement through comprobación to
    recaudación enforcement:

    Attributes:
        DECLARACION_PRESENTADA: A filing was accepted at AEAT (an
            expediente in the declaration register, or a verified
            justificante). The acknowledgement half of the stream.
        ACUSE_RECIBO: An acuse de recibo — a delivery/read receipt for a
            prior notification.
        COMUNICACION: An informational comunicación; no response demanded.
        NOTIFICACION: A formal notificación (legally binding, opens the
            ten-day acuse window). Generic when no sharper category matches.
        REQUERIMIENTO: A requerimiento de información / documentación — a
            demand the taxpayer must answer within a deadline.
        COMPROBACION: The start of a procedimiento de comprobación /
            verificación de datos.
        PROPUESTA_LIQUIDACION: A propuesta de liquidación issued during a
            comprobación, open to allegations before it is confirmed.
        LIQUIDACION: An acuerdo / liquidación (provisional or definitiva)
            settling a debt.
        ACUERDO_SANCION: An acuerdo de inicio (or resolution) of a
            procedimiento sancionador.
        RESOLUCION: A resolución of a procedure or recurso.
        DEVOLUCION: An acuerdo de devolución (refund) event.
        PROVIDENCIA_APREMIO: A providencia de apremio — recaudación opens
            enforced collection with the recargo de apremio.
        DILIGENCIA_EMBARGO: A diligencia de embargo — recaudación seizes
            assets.
        PENDIENTE: A placeholder row AEAT shows for an issued-but-not-yet
            delivered item.
        OTHER: A post-filing event that matched no sharper category.
    """

    DECLARACION_PRESENTADA = "declaracion_presentada"
    ACUSE_RECIBO = "acuse_recibo"
    COMUNICACION = "comunicacion"
    NOTIFICACION = "notificacion"
    REQUERIMIENTO = "requerimiento"
    COMPROBACION = "comprobacion"
    PROPUESTA_LIQUIDACION = "propuesta_liquidacion"
    LIQUIDACION = "liquidacion"
    ACUERDO_SANCION = "acuerdo_sancion"
    RESOLUCION = "resolucion"
    DEVOLUCION = "devolucion"
    PROVIDENCIA_APREMIO = "providencia_apremio"
    DILIGENCIA_EMBARGO = "diligencia_embargo"
    PENDIENTE = "pendiente"
    OTHER = "other"


#: The kinds that demand an operator response or signal an enforcement action
#: against the taxpayer. A pending event of one of these kinds is what the
#: overview flags for attention. Derived from the enum, not hand-listed as bare
#: strings, so a new actionable member cannot silently drop out.
ACTIONABLE_POST_FILING_EVENT_KINDS: frozenset[PostFilingEventKind] = frozenset(
    {
        PostFilingEventKind.REQUERIMIENTO,
        PostFilingEventKind.COMPROBACION,
        PostFilingEventKind.PROPUESTA_LIQUIDACION,
        PostFilingEventKind.LIQUIDACION,
        PostFilingEventKind.ACUERDO_SANCION,
        PostFilingEventKind.PROVIDENCIA_APREMIO,
        PostFilingEventKind.DILIGENCIA_EMBARGO,
    },
)


def post_filing_event_is_actionable(kind: PostFilingEventKind) -> bool:
    """Return ``True`` when ``kind`` demands operator action or is an enforcement act."""
    return kind in ACTIONABLE_POST_FILING_EVENT_KINDS


# Concepto substrings mapped to their category, in priority order: the most
# severe / most specific procedural category wins when a concepto mentions more
# than one term (e.g. "diligencia de embargo por providencia de apremio").
_CONCEPTO_PATTERNS: tuple[tuple[tuple[str, ...], PostFilingEventKind], ...] = (
    (("diligencia de embargo", "embargo"), PostFilingEventKind.DILIGENCIA_EMBARGO),
    (("providencia de apremio", "apremio"), PostFilingEventKind.PROVIDENCIA_APREMIO),
    (("procedimiento sancionador", "sancion", "sancionador"), PostFilingEventKind.ACUERDO_SANCION),
    (("propuesta de liquidacion",), PostFilingEventKind.PROPUESTA_LIQUIDACION),
    (("liquidacion",), PostFilingEventKind.LIQUIDACION),
    (("requerimiento",), PostFilingEventKind.REQUERIMIENTO),
    (
        ("verificacion de datos", "comprobacion limitada", "procedimiento de comprobacion", "comprobacion"),
        PostFilingEventKind.COMPROBACION,
    ),
    (("devolucion",), PostFilingEventKind.DEVOLUCION),
    (("resolucion",), PostFilingEventKind.RESOLUCION),
    (("acuse de recibo", "acuse"), PostFilingEventKind.ACUSE_RECIBO),
)

_TIPO_FALLBACK: dict[str, PostFilingEventKind] = {
    "notificacion": PostFilingEventKind.NOTIFICACION,
    "comunicacion": PostFilingEventKind.COMUNICACION,
    "pendiente": PostFilingEventKind.PENDIENTE,
}


def classify_post_filing_event_kind(
    *,
    concepto: str | None = None,
    tipo: str | None = None,
) -> PostFilingEventKind:
    """Classify one pulled notification / expediente row into a :class:`PostFilingEventKind`.

    Matching runs on an accent- and case-folded view of ``concepto`` in
    :data:`_CONCEPTO_PATTERNS` priority order (recaudación enforcement first,
    down to acuse), so the most severe procedural category wins. When the
    concepto is empty or matches nothing, the coarse ``tipo`` row class
    (``notificacion`` / ``comunicacion`` / ``pendiente``) supplies the
    fallback; anything else resolves to :attr:`PostFilingEventKind.OTHER`.

    Args:
        concepto: The free-text concepto / subject line AEAT prints for the
            row, or ``None`` / empty when unavailable.
        tipo: The coarse row class from the notifications surface
            (``notificacion`` / ``comunicacion`` / ``pendiente``), or
            ``None``.

    Returns:
        The classified :class:`PostFilingEventKind`.
    """
    folded_concepto = _fold(concepto or "")
    if folded_concepto:
        for needles, kind in _CONCEPTO_PATTERNS:
            if any(needle in folded_concepto for needle in needles):
                return kind
    if tipo:
        mapped = _TIPO_FALLBACK.get(_fold(tipo))
        if mapped is not None:
            return mapped
    return PostFilingEventKind.OTHER


__all__ = [
    "ACTIONABLE_POST_FILING_EVENT_KINDS",
    "PostFilingEventKind",
    "classify_post_filing_event_kind",
    "post_filing_event_is_actionable",
]
