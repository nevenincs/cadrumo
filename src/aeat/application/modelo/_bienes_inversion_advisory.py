"""Calculate-path advisory wiring for the capital-goods IVA regularización register.

Modelo 303 casilla ``43`` (Regularización bienes de inversión - Cuota) is
``input_kind = manual``: LIVA arts. 107-110 require an annual comparison against
the year's DEFINITIVE prorrata percentage, and that percentage is itself an
unmodelled, separately-deferred source
(``2026-06-19-silent-zero-base-aggregation-adr`` /
``2026-07-01-iva-complexity-hardening-scope-adr``). Per
``2026-07-01-iva-bienes-inversion-regularizacion-adr`` (Decision 2), the bounded
first slice does not force-fit casilla 43 as a hard binding; instead it reads the
profile-scoped :class:`~aeat.domain.bienes_inversion.BienesInversionIvaRegister`
and, when it holds capital goods in their LIVA art. 107 regularisation window for
the filing year, surfaces a non-blocking
:class:`~aeat.application.aggregation.CalculationSourceDiagnostic` naming the
proposed casilla-43 value (or, absent the deferred definitive-percentage input,
which goods are pending it) — never a silent blank
(``no-silent-under-declaration``).

The register's LIVA art. 107.Siete "último período de liquidación del año
natural" timing means the regularización is due once a year, at the settlement
period (the fourth quarter or the annual period for Modelo 303 filers); this
collector only inspects the register on those periods so a mid-year quarter does
not raise noise for a compute that is not yet due.

This module supplies the ``prorrata_definitiva_by_identifier`` mapping to
:func:`~aeat.application.calculations.build_bienes_inversion_regularizacion_advisory`
as an empty mapping: the current-year definitive percentage is the deferred
input the ADR names, so every in-window good is reported pending it until that
source lands, rather than silently omitted.

See Also:
    :mod:`~aeat.application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the owning
        bucket id.
    :mod:`~aeat.application.calculations._bienes_inversion_regularizacion`:
        Pure advisory-projection function this collector wires to the register.
    :mod:`~aeat.application.bienes_inversion`:
        Application-layer facade exposing the register repository this
        collector loads.
    :mod:`~aeat.domain.bienes_inversion`:
        Register records and the art-109 single-good annual compute.
"""

from __future__ import annotations

from ...core import Modelo
from ...domain.bienes_inversion import BienInversionRecordError
from ..aggregation import CalculationSourceDiagnostic
from ..calculations import build_bienes_inversion_regularizacion_advisory

__all__ = ["collect_bienes_inversion_regularizacion_diagnostics"]

#: Modelo 303 registry period tokens at which the LIVA art. 107.Siete annual
#: regularización settles: the fourth quarter for standard quarterly filers, and
#: the annual period for filers on an annual-only cadence. A mid-year quarter
#: (1T/2T/3T) is never a regularisation event, so the register is not inspected
#: on those periods (no noise for a compute that is not yet due).
_SETTLEMENT_PERIOD_TOKENS: frozenset[str] = frozenset({"4T", "0A"})

_STORAGE_DEGRADED_SOURCE_KIND = "bienes_inversion_register_unreadable"


def collect_bienes_inversion_regularizacion_diagnostics(
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the bienes-de-inversión regularización advisory for one calculation.

    Loads the active bucket's :class:`~aeat.domain.bienes_inversion.BienesInversionIvaRegister`
    and projects it through
    :func:`~aeat.application.calculations.build_bienes_inversion_regularizacion_advisory`
    for ``filing_year``. Returns an empty tuple for every modelo other than
    Modelo 303, for a non-settlement period (the regularización is a once-a-year
    event per LIVA art. 107.Siete), or when the register holds no capital good in
    its regularisation window for the year.

    Args:
        modelo: The modelo identifier of the filing being calculated. Only
            Modelo 303 declares casilla 43; every other modelo returns an empty
            tuple immediately.
        period_token: Bare registry period token for the filing being
            calculated (e.g. ``"4T"``, ``"1T"``, ``"0A"``).
        filing_year: The filing year regularised (the year whose in-window
            goods are compared).
        bucket_id: Bucket identifier the register is loaded from.

    Returns:
        A one-element tuple carrying the advisory when the register holds
        in-window art-108-eligible goods for ``filing_year``, or a
        ``storage_degraded`` diagnostic when the encrypted register cannot be
        read; an empty tuple otherwise.
    """
    if modelo != Modelo.M303.value:
        return ()
    if period_token not in _SETTLEMENT_PERIOD_TOKENS:
        return ()

    from ..bienes_inversion import BienesInversionIvaRegisterRepository

    try:
        register = BienesInversionIvaRegisterRepository(bucket_id=bucket_id).load()
    except BienInversionRecordError as exc:
        return (
            CalculationSourceDiagnostic(
                reason="storage_degraded",
                source_kind=_STORAGE_DEGRADED_SOURCE_KIND,
                message=(f"capital-goods IVA regularización register could not be read (bucket {bucket_id!r}): {exc}"),
            ),
        )
    if not register.records:
        return ()

    _projection, diagnostic = build_bienes_inversion_regularizacion_advisory(
        register,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={},
    )
    if diagnostic is None:
        return ()
    return (diagnostic,)
