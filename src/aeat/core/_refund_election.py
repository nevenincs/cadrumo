"""The operator's per-filing Modelo 303 negative-result disposition election.

The AEAT Modelo 303 "Tipo de declaración" disposition of a negative result is, by
default, a credit carried forward (compensación, ``C``). A taxpayer inscribed in
the Registro de devolución mensual (REDEME) refunds every period under a standing
election; a taxpayer NOT inscribed in REDEME may, in the LAST filing period of the
year (the annual liquidación, Ley 37/1992 art. 116), explicitly elect to request
the credit back as a refund (devolución, ``D``) instead.

This closed value set is declared as a :class:`enum.StrEnum` in ``core`` per the
core-authority discipline (closed axes live in ``core/``, hydrated at boundaries,
asserted as members in tests). It is the operator-input sibling of
:class:`~aeat.core.ResultDisposition` (the fichero result-disposition codes): the
election is what the operator *chooses*, the disposition is what the shared
resolver *derives* from that choice plus the eligibility gate.
"""

from __future__ import annotations

from enum import StrEnum


class RefundElection(StrEnum):
    """The operator's per-filing Modelo 303 negative-result disposition election.

    A non-REDEME taxpayer may, in the last filing period of the year (the annual
    liquidación, Ley 37/1992 art. 116), choose to request a negative result back
    as a refund (``DEVOLVER``) instead of carrying the credit forward
    (``COMPENSAR``). The default is ``COMPENSAR`` — the non-regressive carry-forward
    that requires no opt-in and is the only lawful disposition outside an eligible
    period. ``DEVOLVER`` is the gated opt-in: it is honoured only when the
    eligibility gate permits a refund, and refused otherwise.

    REDEME inscription is the *standing* refund election (every period); this
    per-filing election is the separate, explicit opt-in a non-REDEME taxpayer
    makes for the annual liquidación.
    """

    COMPENSAR = "compensar"
    DEVOLVER = "devolver"


__all__ = ["RefundElection"]
