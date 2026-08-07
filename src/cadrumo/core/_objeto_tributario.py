"""Closed taxonomy of the LGT objects an AEAT-reported deuda can be.

AEAT's *Consultar deudas* listing prints, per outstanding liability, an
*objeto tributario* naming which legal object the debt is: an interés de
demora AEAT itself assessed through its own procedimiento (Ley 58/2003 art.
26.2), a recargo del período ejecutivo once the debt entered apremio (art.
28), a sanción from the régimen sancionador (Título IV), or a liquidación
issued by a comprobación. :class:`ObjetoTributario` is that axis, declared in
``core`` per the core-authority discipline (closed value sets live in ``core/``
as a :class:`enum.StrEnum`, hydrated at the adapter boundary and asserted as
members in tests).

The axis is deliberately SEPARATE from
:class:`~core.PostFilingEventKind` and is never a widening of it. That enum
classifies an *event stream* — a notification or expediente row announcing
that something happened — whereas an objeto tributario classifies a *standing
liability that carries an amount and a procedural state*. An
``ACUERDO_SANCION``-classified notification announces a sanción; the deuda row
is that sanción's resulting debt once liquidated. Two facts about one
procedure, not one fact twice, so they keep different identity, source surface
and lifecycle.

This is a read-and-display classification of what AEAT reported. It never
reaches a modelo casilla: an AEAT-imposed liability is downstream of the
taxpayer's tax position for a period rather than part of it, so no binding
``source`` kind, aggregation channel or casilla resolution consumes it. The
worked counter-example a reader must not miss is M100 casilla ``0576``,
"Intereses de demora", which looks like exactly the box an AEAT-reported
interés de demora should feed and is not: that casilla is the taxpayer
*self-computing* interest while voluntarily regularising a previously-claimed
benefit inside the SAME declaration under art. 26.5, a value the formula
engine derives from the taxpayer's own prior figures.

See Also:
    :class:`~core.DeudaDireccion`
        Whether the reported amount is owed by or refundable to the taxpayer,
        carried as its own axis rather than as the sign of an amount.
"""

from __future__ import annotations

from enum import StrEnum


class ObjetoTributario(StrEnum):
    """Which LGT object an AEAT-reported deuda row is.

    The members are the legal objects AEAT's debts consulta distinguishes, not
    a classification this application invents. ``OTRO`` is the honest
    remainder: AEAT prints objeto tributario labels this axis does not
    enumerate, and mapping an unrecognised one onto a named member would
    assert a legal category the listing did not state.

    Attributes:
        INTERES_DEMORA: An interés de demora AEAT assessed through its own
            procedimiento (Ley 58/2003 art. 26.2). Never the taxpayer's
            self-computed art. 26.5 regularisation interest, which is a
            casilla the formula engine derives.
        RECARGO_APREMIO: A recargo del período ejecutivo — ejecutivo, reducido
            or ordinario — charged once the debt entered período ejecutivo
            (art. 28). Unrelated to the recargo de equivalencia IVA regime
            and to the recargo por declaración extemporánea, both of which are
            separate built mechanisms.
        SANCION: A sanción tributaria under the régimen sancionador (Título
            IV, arts. 178-212).
        LIQUIDACION: A liquidación issued by AEAT, typically the outcome of a
            comprobación or verificación.
        OTRO: Any objeto tributario AEAT reported that this axis does not
            name. Preserves the row rather than discarding a real liability
            or mislabelling it.
    """

    INTERES_DEMORA = "interes_demora"
    RECARGO_APREMIO = "recargo_apremio"
    SANCION = "sancion"
    LIQUIDACION = "liquidacion"
    OTRO = "otro"


__all__ = ["ObjetoTributario"]
