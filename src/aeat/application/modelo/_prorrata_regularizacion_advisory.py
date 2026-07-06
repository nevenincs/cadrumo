"""Calculate-path advisory wiring for the annual prorrata-general regularización.

Modelo 303 casilla ``44`` (Regularización prorrata por porcentaje definitivo -
Cuota) is ``input_kind = manual``: LIVA art. 105.Cuatro requires comparing the
year's DEFINITIVE prorrata percentage (art. 104, computed from the year's
actual annual con-derecho/sin-derecho volumes) against the PROVISIONAL
percentage applied across the year's liquidations (art. 105.Uno — normally the
PRIOR year's definitive percentage). The registry already computes the current
period's definitive percentage from real operator-entered annual volumes
(``iva.prorrata-porcentaje``, fed by ``iva.prorrata-volumen-total`` /
``iva.prorrata-volumen-con-derecho``). The automatic feed is now backed by the
live ``BindingSourceKind.PRORRATA_REGULARIZACION`` resolver when its governed
inputs are available; this collector remains as the no-silent-under-declaration
advisory path for missing or unresolved facts. First, for every period, it reads
the profile-scoped prorrata register and raises a missing-carry advisory when
prorrata applies but the provisional percentage ladder is unresolved. Second,
at the settlement period, it reads the CURRENT year's own registry-computed
prorrata figures (never a fabricated value) and can look up the PRIOR year's
persisted ``iva.prorrata-porcentaje`` observation from the local
:class:`~application.calculations.CalculationObservationRepository` — the
same same-modelo prior-filing lookup pattern
:mod:`~application.modelo._prior_payment_advisory` already uses for the
Modelo 130 casilla-05 carry. When a real prior-year percentage is found, the
pure :func:`~application.calculations.build_prorrata_regularizacion_advisory`
projection runs against real, non-fabricated inputs and its advisory is
surfaced verbatim (never re-implemented). When no prior-year observation
exists (a first-filing ejercicio, or the operator has not yet filed the prior
year through this application), the collector still alerts that a
regularización may be due once the prior-year percentage is available, rather
than silently dropping the check.

The register's LIVA art. 105.Cuatro "último período de liquidación del año
natural" timing means the regularización is due once a year, at the
settlement period (the fourth quarter or the annual period for Modelo 303
filers); the proposed-casilla-44 regularización branch only runs on those
periods, while the missing-provisional-carry branch is intentionally per-period.

See Also:
    :mod:`~application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the
        computed casilla values and the shared observation repository.
    :mod:`~application.calculations._prorrata_regularizacion`:
        Source resolver and advisory-projection functions this collector shares
        with the registry-computed annual prorrata figures.
    :mod:`~application.modelo._bienes_inversion_advisory`:
        Sibling advisory collector for the capital-goods IVA regularización
        (LIVA arts. 107-110), whose settlement-period gating this module
        mirrors.
    :mod:`~application.modelo._prior_payment_advisory`:
        Origin of the same-modelo prior-filing observation lookup pattern
        this collector reuses for the prior-year definitive-percentage carry.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import BindingSourceKind, Modelo
from ...domain.calculations.registry import CasillaId, ModeloRevision
from ...domain.prorrata_register import ProrrataRegisterError
from ..aggregation import CalculationSourceDiagnostic
from ..calculations import (
    CalculationObservationRepository,
    build_prorrata_missing_provisional_advisory,
    build_prorrata_regularizacion_advisory,
    derive_prorrata_applicability,
)
from ..prorrata_register import ProrrataRegisterRepository
from ._semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

__all__ = ["collect_prorrata_regularizacion_diagnostics"]

#: Modelo 303 registry period tokens at which the LIVA art. 105.Cuatro annual
#: regularización settles: the fourth quarter for standard quarterly filers,
#: and the annual period for filers on an annual-only cadence. A mid-year
#: quarter (1T/2T/3T) is never a regularisation event, so this collector is
#: silent on those periods (no noise for a compute that is not yet due).
_SETTLEMENT_PERIOD_TOKENS: frozenset[str] = frozenset({"4T", "0A"})

_VOLUMEN_TOTAL_SEMANTIC_ROLE = "iva_prorrata_volumen_total"
_VOLUMEN_CON_DERECHO_SEMANTIC_ROLE = "iva_prorrata_volumen_con_derecho"
_PORCENTAJE_SEMANTIC_ROLE = "iva_prorrata_porcentaje"
_CUOTA_DEDUCIBLE_TOTAL_SEMANTIC_ROLE = "iva_cuota_deducible_total"

_PENDING_PROVISIONAL_SOURCE_KIND = "prorrata_regularizacion_provisional_pending"


def _casilla_id_for_role(revision: ModeloRevision, semantic_role: str, *, modelo_id: str) -> CasillaId | None:
    try:
        return casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError:
        return None


def _prior_year_definitiva_pct(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    porcentaje_id: CasillaId,
) -> Decimal | None:
    """Return the prior ejercicio's persisted definitive prorrata percentage.

    Scans the local Modelo 303 observation catalogue (mirroring
    :mod:`~application.modelo._prior_payment_advisory`'s same-modelo
    prior-filing lookup) for a settlement-period observation in
    ``filing_year - 1`` that carries a value for ``porcentaje_id`` — the same
    ``iva.prorrata-porcentaje`` canonical casilla id shared by every M303
    revision that declares the prorrata semantic roles. Returns ``None`` when
    no such observation exists — the first-ejercicio / not-yet-filed case the
    caller must surface as a pending advisory rather than a fabricated figure.
    """
    prior_year = filing_year - 1
    for payload in repository.iter_modelo(Modelo.M303.value):
        observation = payload.observation
        if observation.filing_year != prior_year or observation.period not in _SETTLEMENT_PERIOD_TOKENS:
            continue
        value = observation.casilla_values.get(porcentaje_id)
        if value is not None:
            return value
    return None


def collect_prorrata_regularizacion_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
    bucket_id: str | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the annual prorrata-general regularización advisory for one calculation.

    Reads the CURRENT year's registry-computed annual prorrata figures
    (``iva.prorrata-volumen-total``, ``iva.prorrata-volumen-con-derecho``,
    ``iva.prorrata-porcentaje``, ``iva.cuota-deducible-total``) from
    ``casilla_values`` and looks up the PRIOR year's persisted definitive
    percentage from ``observation_repository``. When both are available, the
    pure :func:`~application.calculations.build_prorrata_regularizacion_advisory`
    projection runs and its advisory (or silence, when no regularización is
    due) is returned verbatim. When the prior-year percentage cannot be found,
    a lighter pending advisory fires whenever the current year shows
    exempt-without-right operations (prorrata applies), naming casilla 44 as
    not yet automatically checkable.

    Args:
        revision: The :class:`ModeloRevision` whose casillas are inspected for
            the prorrata semantic roles. Only Modelo 303 revisions declare
            them; every other modelo returns an empty tuple immediately.
        casilla_values: Computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        period_token: Bare registry period token for the filing being
            calculated (e.g. ``"4T"``, ``"1T"``, ``"0A"``).
        filing_year: The filing year regularised (the year whose prior
            ejercicio's percentage is looked up).
        bucket_id: Optional bucket identifier for loading the profile-scoped
            prorrata register. When supplied, unresolved provisional register
            state emits a per-period missing-carry advisory before settlement.
        observation_repository: The local
            :class:`~application.calculations.CalculationObservationRepository`
            scanned for the prior-year definitive-percentage carry.

    Returns:
        A tuple carrying at most one advisory: the pure builder's advisory
        when a prior-year percentage is available, a pending advisory when it
        is not, or an empty tuple when no regularización is due or not yet
        relevant (non-settlement period, no exempt-without-right operations).
    """
    if modelo != Modelo.M303.value:
        return ()

    missing_carry_diagnostics = _missing_carry_diagnostics(
        revision,
        casilla_values,
        modelo=modelo,
        filing_year=filing_year,
        bucket_id=bucket_id,
    )
    if period_token not in _SETTLEMENT_PERIOD_TOKENS:
        return missing_carry_diagnostics

    volumen_total_id = _casilla_id_for_role(revision, _VOLUMEN_TOTAL_SEMANTIC_ROLE, modelo_id=modelo)
    volumen_con_derecho_id = _casilla_id_for_role(revision, _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE, modelo_id=modelo)
    porcentaje_id = _casilla_id_for_role(revision, _PORCENTAJE_SEMANTIC_ROLE, modelo_id=modelo)
    cuota_deducible_id = _casilla_id_for_role(revision, _CUOTA_DEDUCIBLE_TOTAL_SEMANTIC_ROLE, modelo_id=modelo)
    if volumen_total_id is None or volumen_con_derecho_id is None:
        return ()
    if porcentaje_id is None or cuota_deducible_id is None:
        return ()

    volumen_total = casilla_values.get(volumen_total_id, Decimal(0))
    volumen_con_derecho = casilla_values.get(volumen_con_derecho_id, Decimal(0))
    operaciones_sin_derecho_deduccion = volumen_total - volumen_con_derecho
    if operaciones_sin_derecho_deduccion <= Decimal(0):
        return ()

    prorrata_definitiva_pct = casilla_values.get(porcentaje_id, Decimal(0))
    cuotas_soportadas_deducibles = casilla_values.get(cuota_deducible_id, Decimal(0))

    prorrata_provisional_pct = _prior_year_definitiva_pct(
        observation_repository,
        filing_year=filing_year,
        porcentaje_id=porcentaje_id,
    )
    if prorrata_provisional_pct is None:
        pending_diagnostic = CalculationSourceDiagnostic(
            reason="official_box_unpopulated",
            source_kind=_PENDING_PROVISIONAL_SOURCE_KIND,
            message=(
                "Operaciones exentas sin derecho a deducción detectadas en el ejercicio "
                f"{filing_year} (prorrata general, LIVA arts. 104-105): la regularización de "
                "casilla 44 no puede comprobarse automáticamente porque no consta el porcentaje "
                f"de prorrata definitivo de {filing_year - 1} en este equipo. Compruebe manualmente "
                "si procede una regularización antes de presentar."
            ),
            casilla_id=porcentaje_id,
        )
        return missing_carry_diagnostics or (pending_diagnostic,)

    _result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
        regularizacion_year=filing_year,
    )
    if diagnostic is None:
        return missing_carry_diagnostics
    return (*missing_carry_diagnostics, diagnostic)


def _missing_carry_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    bucket_id: str | None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if bucket_id is None:
        return ()

    volumen_total_id = _casilla_id_for_role(revision, _VOLUMEN_TOTAL_SEMANTIC_ROLE, modelo_id=modelo)
    volumen_con_derecho_id = _casilla_id_for_role(revision, _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE, modelo_id=modelo)
    declared_volume_total = casilla_values.get(volumen_total_id) if volumen_total_id is not None else None
    declared_volume_con_derecho = (
        casilla_values.get(volumen_con_derecho_id) if volumen_con_derecho_id is not None else None
    )

    try:
        register = ProrrataRegisterRepository(bucket_id=bucket_id).load()
    except ProrrataRegisterError as exc:
        return (
            CalculationSourceDiagnostic(
                reason="storage_degraded",
                source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
                message=(f"prorrata register could not be read (bucket {bucket_id!r}): {exc}"),
            ),
        )

    applicability = derive_prorrata_applicability(
        register_entries=register.entries_for_ejercicio(filing_year),
        declared_volume_total=declared_volume_total,
        declared_volume_con_derecho=declared_volume_con_derecho,
    )
    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=register.resolve_provisional(filing_year),
        ejercicio=filing_year,
    )
    return () if diagnostic is None else (diagnostic,)
