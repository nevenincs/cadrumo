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
from datetime import datetime
from decimal import Decimal

from ...core import Modelo, ProrrataRegisterRegime
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period, m303_annual_settlement_order_key
from ...domain.iva.prorrata import especial_mandatory_rule
from ...domain.prorrata_register import ProrrataRegisterError
from ..aggregation import CalculationSourceDiagnostic, compute_annual_deducible_totals_by_regime
from ..calculations import (
    CalculationObservationRepository,
    build_prorrata_especial_mandatory_advisory,
    build_prorrata_missing_provisional_advisory,
    build_prorrata_regularizacion_advisory,
    derive_prorrata_applicability,
)
from ..prorrata_register import ProrrataRegisterRepository
from ._semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

__all__ = ["collect_prorrata_regularizacion_diagnostics"]

#: Modelo 303 registry period tokens at which the LIVA art. 105.Cuatro annual
#: regularización settles: the fourth quarter for standard quarterly filers,
#: and the annual period for filers on an annual-only cadence. A mid-year
#: quarter (1T/2T/3T) is never a regularisation event, so this collector is
#: silent on those periods (no noise for a compute that is not yet due).
_VOLUMEN_TOTAL_SEMANTIC_ROLE = "iva_prorrata_volumen_total"
_VOLUMEN_CON_DERECHO_SEMANTIC_ROLE = "iva_prorrata_volumen_con_derecho"
_PORCENTAJE_SEMANTIC_ROLE = "iva_prorrata_porcentaje"
_CUOTA_DEDUCIBLE_TOTAL_SEMANTIC_ROLE = "iva_cuota_deducible_total"

_PENDING_PROVISIONAL_SOURCE_KIND = "prorrata_regularizacion_provisional_pending"

#: Shared ``source_kind`` for both LIVA art. 103.Dos.2.º mandatory-especial
#: settlement diagnostics — the CHECK-branch obligation advisory and the
#: PROMPT-branch classify-to-enable advisory. The distinguishing ``reason``
#: (``prorrata_especial_obligatoria`` vs ``prorrata_especial_check_unavailable``)
#: rides alongside on ``Notice.context`` at the CLI projection.
_ESPECIAL_MANDATORY_SOURCE_KIND = "prorrata_especial_mandatory"


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
    candidates: list[tuple[tuple[int, datetime], Decimal]] = []
    for payload in repository.iter_modelo(Modelo.M303.value):
        observation = payload.observation
        if observation.filing_year != prior_year:
            continue
        settlement_key = m303_annual_settlement_order_key(
            Period.from_year_and_code(observation.filing_year, observation.period),
            payload.captured_at,
        )
        if settlement_key is None:
            continue
        value = observation.casilla_values.get(porcentaje_id)
        if value is not None:
            candidates.append((settlement_key, value))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


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
        A tuple of advisories. At the settlement period it may carry the
        casilla-44 regularización advisory (or the pending-percentage advisory),
        the per-period missing-provisional-carry advisory, and the LIVA
        art. 103.Dos.2.º mandatory-especial advisory (the obligation check
        when both regime totals are honestly computable, or the
        classify-to-enable prompt for a general filer whose especial total is
        not yet derivable). Empty when no advisory fires (non-settlement period,
        no exempt-without-right operations, no resolvable prorrata register).
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
    if not is_m303_annual_settlement_period(Period.from_year_and_code(filing_year, period_token)):
        return missing_carry_diagnostics

    # LIVA art. 103.Dos.2.º mandatory-especial settlement check / prompt. This
    # is independent of the casilla-44 regularización below (it reads the annual
    # ledger totals under both regimes, not the current period's casilla_values),
    # so it is computed once here and appended to every settlement return path —
    # including the early-return paths where the regularización roles are absent.
    especial_diagnostics = _especial_mandatory_diagnostics(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        bucket_id=bucket_id,
    )

    volumen_total_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_TOTAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    volumen_con_derecho_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    porcentaje_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _PORCENTAJE_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    cuota_deducible_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _CUOTA_DEDUCIBLE_TOTAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if volumen_total_id is None or volumen_con_derecho_id is None:
        return especial_diagnostics
    if porcentaje_id is None or cuota_deducible_id is None:
        return especial_diagnostics

    volumen_total = casilla_values.get(volumen_total_id, Decimal(0))
    volumen_con_derecho = casilla_values.get(volumen_con_derecho_id, Decimal(0))
    operaciones_sin_derecho_deduccion = volumen_total - volumen_con_derecho
    if operaciones_sin_derecho_deduccion <= Decimal(0):
        return especial_diagnostics

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
            # Advisory-asserted: the message states a claim spanning both art.
            # 104 (the definitive percentage's own computation) and art. 105
            # (the Cuatro regularización comparison this advisory is about), and
            # the casilla_id's own ref carries only art. 104.
            asserted_legal_refs=("ley-37-1992:art-104", "ley-37-1992:art-105"),
        )
        return (*(missing_carry_diagnostics or (pending_diagnostic,)), *especial_diagnostics)

    _result, diagnostic = build_prorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
        regularizacion_year=filing_year,
    )
    if diagnostic is None:
        return (*missing_carry_diagnostics, *especial_diagnostics)
    return (*missing_carry_diagnostics, diagnostic, *especial_diagnostics)


def _especial_mandatory_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    bucket_id: str | None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the LIVA art. 103.Dos.2.º mandatory-especial settlement diagnostic.

    Computes the ejercicio's whole-year deducible IVA cuota under both prorrata
    regimes (one annual aggregation, two apportionment passes) and branches on
    whether the especial total is honestly computable:

    * CHECK branch (register regime ESPECIAL — the general shadow is mechanical —
      or regime GENERAL with every deducible soportado row classified): run the
      real art. 103.Dos.2.º comparison through
      :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
      and surface its message verbatim as a ``prorrata_especial_obligatoria``
      diagnostic. A non-breach returns nothing (no noise).
    * PROMPT branch (register regime GENERAL with unclassified deducible soportado
      rows — the intended general-filer audience whose especial total is not yet
      derivable): emit one ``prorrata_especial_check_unavailable`` diagnostic that
      names the obligation and the enabling ``--input-classification`` /
      ``elect-especial`` actions, carrying NO fabricated amounts.

    Returns an empty tuple when no register apportionment resolves, the register
    is sectorized (a named v1 deferral), or the bucket id is absent.
    """
    if bucket_id is None:
        return ()
    totals = compute_annual_deducible_totals_by_regime(
        bucket_id=bucket_id,
        ejercicio=filing_year,
        revision=revision,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=bucket_id),
    )
    if totals is None:
        return ()

    especial_total_is_honest = (
        totals.regime is ProrrataRegisterRegime.ESPECIAL or totals.unclassified_deducible_count == 0
    )
    if especial_total_is_honest:
        notice = build_prorrata_especial_mandatory_advisory(
            deduction_under_general=totals.deduction_under_general,
            deduction_under_especial=totals.deduction_under_especial,
            ejercicio=filing_year,
        )
        if notice is None:
            return ()
        return (
            CalculationSourceDiagnostic(
                reason="prorrata_especial_obligatoria",
                source_kind=_ESPECIAL_MANDATORY_SOURCE_KIND,
                message=notice.message,
                # Advisory-asserted: this diagnostic holds no casilla (the annual
                # comparison runs across the whole ejercicio's ledger, not one
                # revision casilla), and its message -- built by
                # build_prorrata_especial_mandatory_advisory -- states the art.
                # 103.Dos.2.º mandatory-especial obligation verbatim.
                asserted_legal_refs=("ley-37-1992:art-103",),
            ),
        )

    rule = especial_mandatory_rule(filing_year)
    exceso = (
        f"en un {rule.margin_percentage} por ciento o más"
        if rule.inclusive
        else f"en más de un {rule.margin_percentage} por ciento"
    )
    return (
        CalculationSourceDiagnostic(
            reason="prorrata_especial_check_unavailable",
            source_kind=_ESPECIAL_MANDATORY_SOURCE_KIND,
            message=(
                f"La prorrata especial puede ser obligatoria para {filing_year} (LIVA art. 103.Dos.2.º: "
                f"se aplica cuando las cuotas deducibles por prorrata general exceden {exceso} "
                "de las que resultarían por la regla especial). La comprobación requiere clasificar "
                "el uso de cada cuota soportada (art. 106): declare '--input-classification' en las "
                "operaciones del ejercicio y, en su caso, ejecute 'app ledger prorrata elect-especial "
                f"--ejercicio {filing_year}'. Quedan {totals.unclassified_deducible_count} operaciones sin clasificar."
            ),
            # Advisory-asserted, no casilla here either: the message states both
            # the art. 103.Dos.2.º mandatory-especial threshold AND the art. 106
            # per-input classification the prompt asks the operator to perform.
            asserted_legal_refs=("ley-37-1992:art-103", "ley-37-1992:art-106"),
        ),
    )


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

    volumen_total_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_TOTAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    volumen_con_derecho_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _VOLUMEN_CON_DERECHO_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
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
