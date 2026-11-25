"""Which one period a factura rectificativa's modification is declared in.

A modification reaches exactly one declaración-liquidación, and which one is
decided by the side, the cause, the direction and the election the law leaves
to the taxpayer. LIVA art. 89.Cinco governs the issuer, art. 114.Dos the
recipient, and the two put different periods on the same document depending on
the ground. Nothing here is derived from the period being calculated: that it
is the period in hand is not evidence that the modification belongs to it.

The issuer's side (art. 89.Cinco):

* an ``aumento`` founded on an art. 80 ground or on an error fundado de derecho
  carries a genuine election, recorded as ``issuer_increase_election``: include
  the difference in "la declaración-liquidación del periodo en que se deba
  efectuar la rectificación", or file a declaración-liquidación rectificativa;
* an ``aumento`` on any other ground carries no election at all and goes to a
  declaración-liquidación rectificativa;
* a ``minoracion`` carries the art. 89.Cinco election, recorded as
  ``issuer_minoracion_election``: the art. 120.3 LGT procedure, or
  regularisation in a declaración-liquidación the taxpayer also records, inside
  the one-year window.

The recipient's side (art. 114.Dos):

* an ``aumento`` carries the art. 114.Dos.1.º election of the reception period
  or a later one, recorded as ``recipient_increase_period``;
* a ``minoracion`` carries no election. Art. 80.Tres and a concurso
  reintegración where the recipient is also in concurso go to the period the
  deduction was exercised in; an error fundado de derecho and the remaining
  art. 80 causes go to the reception period; anything else goes to a
  declaración-liquidación rectificativa.

Art. 80.Tres is admitted on neither side without the operator's attestation of
the RIVA art. 24 obligations, because the application cannot observe a
communication or a remittance.

An election or fact the record does not hold is never assumed. The decision
answers with the field the person opens instead, and the caller blocks naming
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.period import Period, PeriodKind
from ..iva.schema import InvoiceKind
from .enums import RectificationFact

if TYPE_CHECKING:
    from ..calculations.registry.invoice_legal_classification import InvoiceLegalClassificationCatalogue
    from ..calculations.registry.rectification_windows import RectificationPeriodWindows
    from .enums import (
        IssuerIncreaseElection,
        IssuerMinoracionElection,
        RectificationCause,
        RectificationDirection,
    )

__all__ = [
    "DecidedRectificationPeriod",
    "RectificationPeriodRefusal",
    "RectificationPeriodRoute",
    "decide_rectification_period",
    "issuer_minoracion_regularisation_period_outside_window",
    "recipient_increase_period_outside_window",
]


class RectificationPeriodRoute(StrEnum):
    """The legal route by which one modification reaches a declaración-liquidación.

    Each member names the provision that places it, so a disclosure can say
    which route a modification took rather than only that it left this period.
    A route whose declaración-liquidación this application does not produce
    still has a name: the modification is declared, elsewhere, by that route.
    """

    #: Art. 89.Cinco, second paragraph: included in the period the
    #: rectification is effected in.
    ISSUER_INCREASE_IN_PERIOD = "issuer_increase_included_in_period"
    #: Art. 89.Cinco, first paragraph: a declaración-liquidación rectificativa
    #: of the original period, with recargo and interest.
    ISSUER_INCREASE_AUTOLIQUIDACION_RECTIFICATIVA = "issuer_increase_autoliquidacion_rectificativa"
    #: Art. 89.Cinco letter a): the art. 120.3 LGT procedure before the
    #: administration, which no declaración-liquidación here carries.
    ISSUER_MINORACION_PROCEDIMIENTO_120_3_LGT = "issuer_minoracion_procedimiento_120_3_lgt"
    #: Art. 89.Cinco letter b): regularised in the recorded period inside the
    #: one-year window, against reimbursement of the recipient.
    ISSUER_MINORACION_REGULARISATION = "issuer_minoracion_regularizacion_en_autoliquidacion"
    #: Art. 114.Dos.1.º: the recipient's elected period, from the reception
    #: period onwards and inside its window.
    RECIPIENT_INCREASE_ELECTED = "recipient_increase_elected_period"
    #: Art. 114.Dos.2.º, last paragraph: the period the justificante was
    #: received in, for an error fundado de derecho and the remaining art. 80
    #: causes.
    RECIPIENT_MINORACION_RECEPTION = "recipient_minoracion_reception_period"
    #: Art. 114.Dos.2.º, second paragraph, and RIVA art. 24.2.b.3.º: the
    #: period the deduction was exercised in, for art. 80.Tres.
    RECIPIENT_MINORACION_EXERCISED_DEDUCTION = "recipient_minoracion_exercised_deduction_period"
    #: Art. 114.Dos.2.º, first paragraph: a declaración-liquidación
    #: rectificativa with recargo and interest.
    RECIPIENT_MINORACION_AUTOLIQUIDACION_RECTIFICATIVA = "recipient_minoracion_autoliquidacion_rectificativa"


class RectificationPeriodRefusal(StrEnum):
    """Why a stated record still places its modification in no period."""

    #: The cause is art. 80.Tres and the operator stated, rather than left
    #: unstated, that the RIVA art. 24 obligations were NOT met. An explicit
    #: denial is an answer, and the answer refuses the modification: art. 24.1
    #: and art. 24.2 condition it on issue and remittance of the rectificativa.
    ART_80_TRES_OBLIGATIONS_NOT_ATTESTED = "rectification_art_80_tres_obligations_not_attested"


@dataclass(frozen=True, slots=True)
class DecidedRectificationPeriod:
    """Where one modification is declared, or what the record must state first.

    Exactly one of three shapes. ``period`` set is a declaración-liquidación
    this application produces, and ``route`` says on what ground. ``period``
    ``None`` with a ``route`` is a modification declared by a route outside
    these returns, which contributes to no period here and is disclosed rather
    than blocked. ``need`` or ``refusal`` set is a record that places the
    modification nowhere yet; ``need`` names the invoice field the person
    opens.
    """

    route: RectificationPeriodRoute | None = None
    period: Period | None = None
    need: RectificationFact | None = None
    refusal: RectificationPeriodRefusal | None = None


def decide_rectification_period(
    *,
    kind: InvoiceKind,
    cause: RectificationCause | None,
    direction: RectificationDirection | None,
    issued_at: date,
    document_received_on: date | None,
    issuer_increase_election: IssuerIncreaseElection | None,
    issuer_minoracion_election: IssuerMinoracionElection | None,
    issuer_minoracion_regularisation_period: Period | None,
    recipient_increase_period: Period | None,
    art_80_tres_obligations_attested: bool | None,
    exercised_deduction_period: Period | None,
    cadence: PeriodKind,
    catalogue: InvoiceLegalClassificationCatalogue,
) -> DecidedRectificationPeriod:
    """Decide the one period ``kind``, ``cause``, ``direction`` and the elections place the modification in.

    ``cadence`` is the cadence of the declaración-liquidación being prepared,
    which is what turns a date into a period: the same reception date is a
    quarter for a quarterly filer and a month for a monthly one. It selects no
    period by itself and never overrides a recorded election.

    Core types:
    :class:`~cadrumo.core.period.Period`,
    :class:`~cadrumo.domain.calculations.registry.invoice_legal_classification.InvoiceLegalClassificationCatalogue`.
    """
    if cause is None:
        return DecidedRectificationPeriod(need=RectificationFact.RECTIFICATION_CAUSE)
    if direction is None:
        return DecidedRectificationPeriod(need=RectificationFact.RECTIFICATION_DIRECTION)
    if cause == catalogue.art_80_tres_cause_token:
        attested = _art_80_tres_attestation(art_80_tres_obligations_attested)
        if attested is not None:
            return attested
    minoracion = direction == catalogue.minoracion_token
    if kind is InvoiceKind.ISSUED:
        return _issued_period(
            cause=cause,
            minoracion=minoracion,
            issued_at=issued_at,
            increase_election=issuer_increase_election,
            minoracion_election=issuer_minoracion_election,
            regularisation_period=issuer_minoracion_regularisation_period,
            cadence=cadence,
            catalogue=catalogue,
        )
    return _received_period(
        cause=cause,
        minoracion=minoracion,
        document_received_on=document_received_on,
        recipient_increase_period=recipient_increase_period,
        exercised_deduction_period=exercised_deduction_period,
        cadence=cadence,
        catalogue=catalogue,
    )


def _art_80_tres_attestation(attested: bool | None) -> DecidedRectificationPeriod | None:
    """Hold an art. 80.Tres modification until the RIVA art. 24 obligations are attested."""
    if attested is None:
        return DecidedRectificationPeriod(need=RectificationFact.ART_80_TRES_OBLIGATIONS_ATTESTED)
    if not attested:
        return DecidedRectificationPeriod(refusal=RectificationPeriodRefusal.ART_80_TRES_OBLIGATIONS_NOT_ATTESTED)
    return None


def _issued_period(
    *,
    cause: RectificationCause,
    minoracion: bool,
    issued_at: date,
    increase_election: IssuerIncreaseElection | None,
    minoracion_election: IssuerMinoracionElection | None,
    regularisation_period: Period | None,
    cadence: PeriodKind,
    catalogue: InvoiceLegalClassificationCatalogue,
) -> DecidedRectificationPeriod:
    """Place an issued modification under LIVA art. 89.Cinco."""
    if not minoracion:
        if cause not in catalogue.art_80_cause_choices and cause != catalogue.error_fundado_de_derecho_cause_token:
            # Art. 89.Cinco's first paragraph is the rule and its second the
            # exception, so a ground outside art. 80 and outside the error
            # fundado de derecho has no election to record.
            return DecidedRectificationPeriod(
                route=RectificationPeriodRoute.ISSUER_INCREASE_AUTOLIQUIDACION_RECTIFICATIVA,
            )
        if increase_election is None:
            return DecidedRectificationPeriod(need=RectificationFact.ISSUER_INCREASE_ELECTION)
        if increase_election == catalogue.issuer_autoliquidacion_rectificativa_token:
            return DecidedRectificationPeriod(
                route=RectificationPeriodRoute.ISSUER_INCREASE_AUTOLIQUIDACION_RECTIFICATIVA,
            )
        return DecidedRectificationPeriod(
            route=RectificationPeriodRoute.ISSUER_INCREASE_IN_PERIOD,
            period=_rectification_period(issued_at, cadence),
        )
    if minoracion_election is None:
        return DecidedRectificationPeriod(need=RectificationFact.ISSUER_MINORACION_ELECTION)
    if minoracion_election == catalogue.procedimiento_120_3_lgt_token:
        return DecidedRectificationPeriod(route=RectificationPeriodRoute.ISSUER_MINORACION_PROCEDIMIENTO_120_3_LGT)
    if regularisation_period is None:
        return DecidedRectificationPeriod(need=RectificationFact.ISSUER_MINORACION_REGULARISATION_PERIOD)
    return DecidedRectificationPeriod(
        route=RectificationPeriodRoute.ISSUER_MINORACION_REGULARISATION,
        period=regularisation_period,
    )


def _received_period(
    *,
    cause: RectificationCause,
    minoracion: bool,
    document_received_on: date | None,
    recipient_increase_period: Period | None,
    exercised_deduction_period: Period | None,
    cadence: PeriodKind,
    catalogue: InvoiceLegalClassificationCatalogue,
) -> DecidedRectificationPeriod:
    """Place a received modification under LIVA art. 114.Dos."""
    if document_received_on is None:
        # Both branches read the reception: the increase's own window starts
        # there and the minoración's period IS it.
        return DecidedRectificationPeriod(need=RectificationFact.DOCUMENT_RECEIVED_ON)
    if not minoracion:
        if recipient_increase_period is None:
            return DecidedRectificationPeriod(need=RectificationFact.RECIPIENT_INCREASE_PERIOD)
        return DecidedRectificationPeriod(
            route=RectificationPeriodRoute.RECIPIENT_INCREASE_ELECTED,
            period=recipient_increase_period,
        )
    if cause == catalogue.art_80_tres_cause_token:
        if exercised_deduction_period is None:
            return DecidedRectificationPeriod(need=RectificationFact.EXERCISED_DEDUCTION_PERIOD)
        return DecidedRectificationPeriod(
            route=RectificationPeriodRoute.RECIPIENT_MINORACION_EXERCISED_DEDUCTION,
            period=exercised_deduction_period,
        )
    if cause in catalogue.art_80_cause_choices or cause == catalogue.error_fundado_de_derecho_cause_token:
        return DecidedRectificationPeriod(
            route=RectificationPeriodRoute.RECIPIENT_MINORACION_RECEPTION,
            period=_rectification_period(document_received_on, cadence),
        )
    return DecidedRectificationPeriod(
        route=RectificationPeriodRoute.RECIPIENT_MINORACION_AUTOLIQUIDACION_RECTIFICATIVA,
    )


def _rectification_period(day: date, cadence: PeriodKind) -> Period:
    """The declaración-liquidación of ``cadence`` whose span holds ``day``."""
    return Period.containing(day, cadence)


def issuer_minoracion_regularisation_period_outside_window(
    *,
    issued_at: date,
    period: Period,
    windows: RectificationPeriodWindows,
) -> bool:
    """Whether an elected art. 89.Cinco letter b) period falls outside its window.

    Letter b) admits "la declaración-liquidación correspondiente al periodo en
    que deba efectuarse la rectificación o ... las posteriores hasta el plazo de
    un año a contar desde el momento en que debió efectuarse la mencionada
    rectificación". The issue date of the rectificativa is when the
    rectification was effected, by RD 1619/2012 art. 15.3's expedición
    obligation, and it is the only such date this record holds. So the window
    runs from that date's own period to the period one declared year later.

    Core types:
    :class:`~cadrumo.core.period.Period`,
    :class:`~cadrumo.domain.calculations.registry.rectification_windows.RectificationPeriodWindows`.
    """
    return _outside_window(
        floor_day=issued_at,
        ceiling_day=_years_after(issued_at, windows.issuer_minoracion_regularisation_years),
        period=period,
    )


def recipient_increase_period_outside_window(
    *,
    cause: RectificationCause,
    issued_at: date,
    document_received_on: date,
    period: Period,
    windows: RectificationPeriodWindows,
    catalogue: InvoiceLegalClassificationCatalogue,
) -> bool:
    """Whether an elected art. 114.Dos.1.º period falls outside its window.

    The floor is the reception period, which the article names first. The
    ceiling is four years from the circumstances that modify the base for an
    art. 80 ground, and one year from the justificante's expedición for any
    other ground, as the apartado's second paragraph requires. The
    rectificativa's own issue date stands for both: art. 15.3 RD 1619/2012 ties
    expedición to the circumstance, and the devengo of the original operation
    is not a fact this record carries.

    Core types:
    :class:`~cadrumo.core.period.Period`,
    :class:`~cadrumo.domain.calculations.registry.rectification_windows.RectificationPeriodWindows`,
    :class:`~cadrumo.domain.calculations.registry.invoice_legal_classification.InvoiceLegalClassificationCatalogue`.
    """
    years = (
        windows.recipient_increase_years
        if cause in catalogue.art_80_cause_choices
        else windows.recipient_increase_non_art_80_years
    )
    return _outside_window(
        floor_day=document_received_on,
        ceiling_day=_years_after(issued_at, years),
        period=period,
    )


def _outside_window(*, floor_day: date, ceiling_day: date, period: Period) -> bool:
    """Whether ``period`` neither holds nor follows ``floor_day``, or begins after ``ceiling_day``.

    A period that holds the floor day is admitted whole, because the law names
    that declaración-liquidación itself rather than the days inside it. The
    ceiling is read on the period's start, because a declaración-liquidación is
    presented for a period that had begun before the limit expired.
    """
    if not period.has_date_span():
        return True
    return period.end_date < floor_day or period.start_date > ceiling_day


def _years_after(day: date, years: int) -> date:
    """The same calendar day ``years`` whole years later, 29 February becoming 28 February."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=day.day - 1)
