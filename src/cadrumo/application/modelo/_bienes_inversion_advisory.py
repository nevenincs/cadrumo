"""Calculate-path advisory wiring for the capital-goods IVA regularización register.

Modelo 303 casilla ``43`` (Regularización bienes de inversión - Cuota) is
``input_kind = manual``: LIVA arts. 107-110 require a governed feed from the
profile-scoped capital-goods register, the current-year definitive prorrata
percentage, and art-110 disposal cap facts before the source can become a hard
binding. Casilla 43 is deliberately not force-fit as a hard binding; instead
this reads the profile-scoped
:class:`~domain.bienes_inversion.BienesInversionIvaRegister` and, when it holds
capital goods in their LIVA art. 107 regularisation window for the filing year,
surfaces a non-blocking
:class:`~application.aggregation.CalculationSourceDiagnostic` naming the
proposed casilla-43 value (or, absent the deferred definitive-percentage input,
which goods are pending it) — never a silent blank. A good the register records
as disposed of (art. 110 entrega) during the filing year is routed instead
through the single ("única") disposal regularización, which carries no pending
state: every fact art. 110 needs is already on the record, so the advisory always
names a concrete proposed figure.

The register's LIVA art. 107.Siete "último período de liquidación del año
natural" timing means the regularización is due once a year, at the settlement
period (the fourth quarter or the annual period for Modelo 303 filers); this
collector only inspects the register on those periods so a mid-year quarter does
not raise noise for a compute that is not yet due.

This module supplies the ``prorrata_definitiva_by_identifier`` mapping to
:func:`~application.calculations.build_bienes_inversion_regularizacion_advisory`
as an empty mapping: until a bienes-inversion source resolver maps the live
prorrata percentage onto each register row and binding target, every in-window,
non-disposed good is reported pending that source input rather than silently
omitted. It likewise supplies no
``cuota_devengada_entrega_by_identifier`` to
:func:`~application.calculations.build_bienes_inversion_transmision_advisory`,
so the regla-1ª cap stays unapplied until the operator's own cuota devengada on
the disposal is captured — the disposal figure itself is never withheld pending
that cap.

See Also:
    :mod:`~application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the owning
        bucket id.
    :mod:`~application.calculations._bienes_inversion_regularizacion`:
        Pure advisory-projection functions this collector wires to the register.
    :mod:`~application.bienes_inversion`:
        Application-layer facade exposing the register repository this
        collector loads.
    :mod:`~domain.bienes_inversion`:
        Register records, the art-109 annual compute, and the art-110 disposal
        compute.
"""

from __future__ import annotations

from ...core import Modelo, Period
from ...domain.bienes_inversion import BienInversionRecordError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period
from ..aggregation import CalculationSourceDiagnostic
from ..bienes_inversion import BienesInversionIvaRegisterRepository
from ..calculations import (
    build_bienes_inversion_regularizacion_advisory,
    build_bienes_inversion_transmision_advisory,
)

__all__ = ["collect_bienes_inversion_regularizacion_diagnostics"]

#: Modelo 303 registry period tokens at which the LIVA art. 107.Siete annual
#: regularización settles: the fourth quarter for standard quarterly filers, and
#: the annual period for filers on an annual-only cadence. A mid-year quarter
#: (1T/2T/3T) is never a regularisation event, so the register is not inspected
#: on those periods (no noise for a compute that is not yet due).
_STORAGE_DEGRADED_SOURCE_KIND = "bienes_inversion_register_unreadable"


def collect_bienes_inversion_regularizacion_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the bienes-de-inversión regularización advisories for one calculation.

    Loads the active bucket's :class:`~domain.bienes_inversion.BienesInversionIvaRegister`
    and projects it through both
    :func:`~application.calculations.build_bienes_inversion_regularizacion_advisory`
    (the ordinary annual art-109 comparison, for in-window, non-disposed goods)
    and
    :func:`~application.calculations.build_bienes_inversion_transmision_advisory`
    (the art-110 single disposal regularización, for a good disposed of during
    ``filing_year``) for ``filing_year``. Returns an empty tuple for every modelo
    other than Modelo 303, for a non-settlement period (the regularización is a
    once-a-year event per LIVA art. 107.Siete), or when the register holds
    neither an in-window good nor a disposal for the year.

    Args:
        revision: The :class:`ModeloRevision` being calculated, read only for
            casilla 43's own registry grounding -- never for a legal figure.
        modelo: The modelo identifier of the filing being calculated. Only
            Modelo 303 declares casilla 43; every other modelo returns an empty
            tuple immediately.
        period_token: Bare registry period token for the filing being
            calculated (e.g. ``"4T"``, ``"1T"``, ``"0A"``).
        filing_year: The filing year regularised (the year whose in-window
            goods are compared, and whose disposals are regularised).
        bucket_id: Bucket identifier the register is loaded from.

    Returns:
        A tuple carrying the annual advisory and/or the disposal advisory when
        the register holds in-window art-108-eligible goods and/or a disposal
        for ``filing_year``, or a one-element ``storage_degraded`` diagnostic
        when the encrypted register cannot be read; an empty tuple otherwise.
    """
    if modelo != Modelo.M303.value:
        return ()
    if not is_m303_annual_settlement_period(Period.from_year_and_code(filing_year, period_token)):
        return ()

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

    diagnostics: list[CalculationSourceDiagnostic] = []

    _annual_projection, annual_diagnostic = build_bienes_inversion_regularizacion_advisory(
        revision,
        register,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={},
    )
    if annual_diagnostic is not None:
        diagnostics.append(annual_diagnostic)

    _transmision_projection, transmision_diagnostic = build_bienes_inversion_transmision_advisory(
        revision,
        register,
        disposal_year=filing_year,
    )
    if transmision_diagnostic is not None:
        diagnostics.append(transmision_diagnostic)

    return tuple(diagnostics)
