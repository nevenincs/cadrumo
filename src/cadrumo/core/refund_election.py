"""The operator's per-filing Modelo 303 negative-result disposition election.

The AEAT Modelo 303 "Tipo de declaración" disposition of a negative result is, by
default, a credit carried forward (compensación, ``C``). A taxpayer inscribed in
the Registro de devolución mensual (REDEME) is treated as having a standing
monthly-devolución disposition policy; a taxpayer NOT inscribed
in REDEME may, in the LAST filing period of the year (the annual liquidación, Ley
37/1992 art. 116), explicitly elect to request devolución (``D``) instead.

The exported :class:`RefundElection` closed value set is declared as a
:class:`enum.StrEnum` in ``core`` per the core-authority discipline (closed axes
live in ``core/``, hydrated at boundaries, asserted as members in tests). It is
the operator-input sibling of :class:`~core.ResultDisposition` (the fichero
result-disposition codes): the election is what the operator *chooses*, while
:func:`~application.modelo._result_disposition_resolution.resolve_modelo_result_disposition` derives the
filed disposition from that choice plus the
:func:`~domain.iva.refund_disposition_available` eligibility gate.

The enum is threaded by :class:`~application.modelo.ModeloExportCommand`
and :func:`~application.modelo.file_modelo_revision` into the same
disposition resolver that
:func:`application.modelo._result_disposition_resolution.revision_is_refund_disposition`
uses for cross-period carry. It is not the refund account itself: the
cuenta-devolución data lives in :class:`~domain.deadlines.RefundAccount`,
and a refund disposition without that account is refused downstream by the
export path.
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

    REDEME inscription is treated as the standing monthly-devolución
    disposition policy; this per-filing election is the separate, explicit
    opt-in a non-REDEME taxpayer makes for the annual liquidación.

    Attributes:
        COMPENSAR: Keep the negative result as compensación (``C``), the default
            carry-forward disposition.
        DEVOLVER: Request devolución (``D``) through the shared Modelo 303
            resolver. The resolver honours it only when
            :func:`domain.iva.refund_disposition_available` says the period
            can lawfully refund; otherwise it raises the application-level
            refund-election refusal.
    """

    COMPENSAR = "compensar"
    DEVOLVER = "devolver"


__all__ = ["RefundElection"]
