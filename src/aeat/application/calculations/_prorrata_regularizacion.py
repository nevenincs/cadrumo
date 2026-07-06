"""Advisory projection for the annual prorrata-general regularización (LIVA arts. 104-105).

Builds the projection and live source resolver for Modelo 303 casilla 44
(Regularización prorrata por porcentaje definitivo - Cuota) and the Modelo 390
annual regularización field when a taxpayer under prorrata general has
exempt-without-right operations in the year and a provisional percentage was
applied. The calculate path still keeps the advisory surface so missing
provisional/current-year inputs never collapse into a silent zero.

This is a pure function over the two prorrata percentages and the year's
deductible input IVA, plus a resolver that consumes the governed prorrata
register or a stamped prior-year settlement observation for the provisional
percentage. The definitive percentage itself comes from the full-year volume
rollup fed to
:func:`~domain.iva.compute_prorrata_definitiva_anual`; deriving it from a
single quarter is a correctness defect (the silent-zero-base ADR).

See Also:
    :func:`~domain.iva.compute_regularizacion_prorrata_anual`
        Pure LIVA art. 105.Cuatro computation consumed by this projection.
    :mod:`~application.modelo._prorrata_regularizacion_advisory`
        Calculate-path collector that calls this advisory projection from
        Modelo 303 values and prior-year observations.
    :mod:`~application.aggregation._iva_ledger`
        Source of typed IVA ledger observations used for declared-volume
        divergence checks.
    :mod:`~domain.prorrata_register`
        Cross-period carry home for provisional and definitive prorrata
        percentages.
    :mod:`~application.calculations.tests.test_prorrata_regularizacion`
        Focused regressions for live-feed and ledger-divergence behavior.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from pydantic import BaseModel

from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ...adapters.persistence.storage import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import (
    STRICT_FROZEN_CONFIG,
    BindingSourceKind,
    CasillaId,
    Modelo,
    Period,
    ProrrataRegisterRegime,
    validated_casilla_id,
)
from ...domain.calculations.registry import (
    BindingId,
    IvaLedgerObservation,
    LegalRefId,
    ModeloRevision,
    RegistrySnapshot,
    SourceRefId,
)
from ...domain.iva import (
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    RegularizacionProrrataDireccion,
    RegularizacionProrrataResult,
    compute_regularizacion_prorrata_anual,
)
from ...domain.prorrata_register import (
    ProrrataProvisionalResolution,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
)
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

#: The Modelo 303 casilla the annual prorrata regularización feeds. Deducciones
#: block, "Regularización prorrata por porcentaje definitivo - Cuota"
#: (LIVA art. 105.Cuatro).
CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA: CasillaId = validated_casilla_id(
    "44",
    surface="annual prorrata regularizacion Modelo 303 casilla",
)

_SOURCE_KIND: Final = BindingSourceKind.PRORRATA_REGULARIZACION
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError, ProrrataRegisterError)
_LEDGER_VOLUME_DIVERGENCE_SOURCE_KIND = "prorrata_regularizacion_ledger_volume_divergence"
_OUTPUT_MODELO_303_CASILLA_44: Final = "modelo_303_casilla_44"
_OUTPUT_MODELO_390_REGULARIZACION_ANUAL: Final = "modelo_390_regularizacion_anual"
_ZERO: Final = Decimal("0.00")
_SETTLEMENT_PERIOD_TOKENS: Final[tuple[str, ...]] = ("4T", "0A")
_SETTLEMENT_PERIOD_ORDER: Final[dict[str, int]] = {
    period: index for index, period in enumerate(_SETTLEMENT_PERIOD_TOKENS)
}
_SOURCE_PERIODS: Final[tuple[str, ...]] = ("1T", "2T", "3T", "4T")
_CUOTA_DEDUCIBLE_TOTAL_ID: Final[CasillaId] = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="prorrata regularizacion source casilla",
)
_VOLUMEN_CON_DERECHO_ID: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="prorrata regularizacion source casilla",
)
_VOLUMEN_TOTAL_ID: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-volumen-total",
    surface="prorrata regularizacion source casilla",
)
_PORCENTAJE_ID: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata regularizacion source casilla",
)
_SOURCE_CASILLA_IDS: Final[tuple[CasillaId, ...]] = (
    _CUOTA_DEDUCIBLE_TOTAL_ID,
    _VOLUMEN_CON_DERECHO_ID,
    _VOLUMEN_TOTAL_ID,
    _PORCENTAJE_ID,
)
_CON_DERECHO_OUTPUT_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.DOMESTIC_GENERAL_21,
        IvaCategory.DOMESTIC_REDUCED_10,
        IvaCategory.DOMESTIC_SUPER_REDUCED_4,
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    },
)
_CON_DERECHO_EXEMPTION_ARTICLES: frozenset[IvaExemptionArticle] = frozenset({IvaExemptionArticle.ART_20_UNO_26})


@dataclass(frozen=True, slots=True)
class _PriorDefinitivaCarry:
    percentage: Decimal
    source_filing_year: int
    source_period: str


@dataclass(frozen=True, slots=True)
class _CurrentYearSourcePeriodFeed:
    values: Mapping[CasillaId, Decimal]
    source_periods: tuple[str, ...]
    missing_source_periods: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing_source_periods


class ProrrataRegularizacionFeedProjection(BaseModel):
    """Structured proposed feeds for annual prorrata-general regularización.

    These values feed the live source resolver and the operator-facing advisory
    for Modelo 303 casilla 44 and the Modelo 390 annual regularización field.
    Both come from the same
    :class:`RegularizacionProrrataResult`, preserving the registry's declared
    annual-volume authority for the definitive percentage.

    See Also:
        :func:`project_prorrata_regularizacion_feed`
            Constructs this carrier from the pure annual regularización result.
    """

    model_config = STRICT_FROZEN_CONFIG

    result: RegularizacionProrrataResult
    operaciones_sin_derecho_deduccion: Decimal
    modelo_303_casilla_44_id: CasillaId = CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA
    modelo_303_casilla_44_value: Decimal | None = None
    modelo_390_regularizacion_anual_value: Decimal | None = None


class ProrrataDeclaredVolumeLedgerRollup(BaseModel):
    """Ledger-side annual volume rollup used only as a divergence advisory.

    Declared annual volume casillas remain the filing authority. This projection
    records the currently classifiable ledger output-volume view so settlement
    can warn when it contradicts those declared values.

    See Also:
        :func:`build_prorrata_declared_volume_divergence_advisory`
            Builds this rollup and the optional non-blocking diagnostic.
    """

    model_config = STRICT_FROZEN_CONFIG

    declared_volume_total: Decimal
    declared_volume_con_derecho: Decimal
    declared_volume_sin_derecho: Decimal
    ledger_volume_total: Decimal
    ledger_volume_con_derecho: Decimal
    ledger_volume_sin_derecho: Decimal
    included_ledger_ids: tuple[str, ...] = ()

    @property
    def diverges(self) -> bool:
        return (
            self.declared_volume_total != self.ledger_volume_total
            or self.declared_volume_con_derecho != self.ledger_volume_con_derecho
            or self.declared_volume_sin_derecho != self.ledger_volume_sin_derecho
        )


class ProrrataApplicabilityProjection(BaseModel):
    """Fail-closed-to-visible prorrata applicability evidence for one ejercicio.

    Prorrata applies when the taxpayer has an active register entry or the
    ejercicio shows exempt-without-right operations through declared annual
    volumes or the ledger rollup. This projection is deliberately pure; later
    steps turn an applicable-but-unresolved state into calculate/verify
    diagnostics.
    """

    model_config = STRICT_FROZEN_CONFIG

    applies: bool
    register_active: bool
    declared_volume_sin_derecho: Decimal
    ledger_volume_sin_derecho: Decimal
    evidence_kinds: tuple[str, ...] = ()


def derive_prorrata_applicability(
    *,
    register_entries: Iterable[ProrrataRegisterEntry] = (),
    declared_volume_total: Decimal | None = None,
    declared_volume_con_derecho: Decimal | None = None,
    ledger_rollup: ProrrataDeclaredVolumeLedgerRollup | None = None,
) -> ProrrataApplicabilityProjection:
    """Derive whether prorrata applies for an ejercicio.

    The rule is intentionally fail-closed-to-visible: any active register entry
    (``general`` or ``especial``), any positive declared sin-derecho annual
    volume, or any positive ledger-projected sin-derecho annual volume means
    prorrata applies and later steps must not silently assume a full-deduction
    default.
    """
    if (declared_volume_total is None) != (declared_volume_con_derecho is None):
        raise ValueError("declared_volume_total and declared_volume_con_derecho must be supplied together")

    entries = tuple(register_entries)
    register_active = any(entry.regime is not ProrrataRegisterRegime.NINGUNA for entry in entries)
    declared_volume_sin_derecho = (
        Decimal("0")
        if declared_volume_total is None or declared_volume_con_derecho is None
        else declared_volume_total - declared_volume_con_derecho
    )
    ledger_volume_sin_derecho = Decimal("0") if ledger_rollup is None else ledger_rollup.ledger_volume_sin_derecho

    evidence: list[str] = []
    if register_active:
        evidence.append("register_active")
    if declared_volume_sin_derecho > Decimal("0"):
        evidence.append("declared_sin_derecho_volume")
    if ledger_volume_sin_derecho > Decimal("0"):
        evidence.append("ledger_sin_derecho_volume")

    return ProrrataApplicabilityProjection(
        applies=bool(evidence),
        register_active=register_active,
        declared_volume_sin_derecho=declared_volume_sin_derecho,
        ledger_volume_sin_derecho=ledger_volume_sin_derecho,
        evidence_kinds=tuple(evidence),
    )


def build_prorrata_missing_provisional_advisory(
    *,
    applicability: ProrrataApplicabilityProjection,
    provisional_resolution: ProrrataProvisionalResolution,
    ejercicio: int,
    first_ejercicio: bool = False,
) -> CalculationSourceDiagnostic | None:
    """Build the visible advisory for an applicable prorrata with no provisional percentage.

    This is the per-period no-silent-under-declaration warning. It does not
    fabricate a percentage: an applicable-but-unresolved prorrata tells the
    operator to record the inicio-de-actividad percentage for a first ejercicio
    or seed/record the prior definitive percentage for subsequent ejercicios.
    """
    if not applicability.applies or provisional_resolution.resolved:
        return None

    operator_action = (
        "registre el porcentaje provisional de inicio de actividad"
        if first_ejercicio
        else "siembre o registre la prorrata definitiva del ejercicio anterior"
    )
    evidence = ", ".join(applicability.evidence_kinds) or "prorrata_applicability"
    message = (
        f"Prorrata aplicable en {ejercicio} sin porcentaje provisional resuelto "
        f"({evidence}). {operator_action}; no se aplica un porcentaje por defecto."
    )
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
        casilla_id=CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA,
    )


def build_prorrata_declared_volume_divergence_advisory(
    *,
    declared_volume_total: Decimal,
    declared_volume_con_derecho: Decimal,
    ledger_observations: Iterable[IvaLedgerObservation],
    ejercicio_periods: Iterable[Period],
    regularizacion_year: int,
) -> tuple[ProrrataDeclaredVolumeLedgerRollup, CalculationSourceDiagnostic | None]:
    """Compare declared annual prorrata volumes with the ledger rollup.

    The rollup is deliberately advisory-only: it uses the existing IVA ledger
    observation stream and the supplied ejercicio periods'
    :meth:`~core.Period.contains` boundary, but it does not replace the operator's
    declared annual volume casillas because some art-104 exclusions still need
    explicit classification.

    See Also:
        :class:`~domain.calculations.registry.IvaLedgerObservation`
            Typed ledger observation stream classified into con-derecho and
            sin-derecho output volumes.
    """
    periods = tuple(ejercicio_periods)
    if not periods:
        raise ValueError("ejercicio_periods must contain at least one Period")

    ledger_volume_con_derecho = Decimal("0")
    ledger_volume_sin_derecho = Decimal("0")
    included_ledger_ids: list[str] = []
    for observation in ledger_observations:
        if not any(period.contains(observation.transaction_date) for period in periods):
            continue
        volume_side = _prorrata_volume_side(observation)
        if volume_side is None:
            continue
        included_ledger_ids.append(observation.ledger_id)
        if volume_side == "con_derecho":
            ledger_volume_con_derecho += observation.base_amount
        else:
            ledger_volume_sin_derecho += observation.base_amount

    declared_volume_sin_derecho = declared_volume_total - declared_volume_con_derecho
    rollup = ProrrataDeclaredVolumeLedgerRollup(
        declared_volume_total=declared_volume_total,
        declared_volume_con_derecho=declared_volume_con_derecho,
        declared_volume_sin_derecho=declared_volume_sin_derecho,
        ledger_volume_total=ledger_volume_con_derecho + ledger_volume_sin_derecho,
        ledger_volume_con_derecho=ledger_volume_con_derecho,
        ledger_volume_sin_derecho=ledger_volume_sin_derecho,
        included_ledger_ids=tuple(sorted(included_ledger_ids)),
    )
    if not rollup.diverges:
        return rollup, None

    diagnostic = CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_LEDGER_VOLUME_DIVERGENCE_SOURCE_KIND,
        message=(
            f"Volúmenes anuales de prorrata declarados para {regularizacion_year} difieren del rollup "
            f"IVA de libro: declarado con derecho {declared_volume_con_derecho}, sin derecho "
            f"{declared_volume_sin_derecho}; libro con derecho {ledger_volume_con_derecho}, "
            f"sin derecho {ledger_volume_sin_derecho}. Las casillas declaradas conservan la autoridad."
        ),
    )
    return rollup, diagnostic


def _prorrata_volume_side(observation: IvaLedgerObservation) -> str | None:
    if observation.flow_direction is not IvaFlowDirection.REPERCUTIDO:
        return None
    if observation.category is IvaCategory.DOMESTIC_EXEMPT:
        if observation.exemption_article in _CON_DERECHO_EXEMPTION_ARTICLES:
            return "con_derecho"
        return "sin_derecho"
    if observation.category in _CON_DERECHO_OUTPUT_CATEGORIES:
        return "con_derecho"
    return None


def project_prorrata_regularizacion_feed(
    *,
    cuotas_soportadas_deducibles: Decimal,
    prorrata_provisional_pct: Decimal,
    prorrata_definitiva_pct: Decimal,
    operaciones_sin_derecho_deduccion: Decimal,
) -> ProrrataRegularizacionFeedProjection:
    """Project the annual regularización onto the M303 and M390 filing targets.

    ``prorrata_definitiva_pct`` is supplied by the registry-computed annual
    volume casillas. This helper deliberately does not recompute that
    percentage; it turns the pure art-105 result into the two filing values used
    by the live resolver and the advisory surface.

    See Also:
        :class:`ProrrataRegularizacionFeedProjection`
            Structured carrier for the two proposed filing values.
    """
    result = compute_regularizacion_prorrata_anual(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
    )
    proposed_value = (
        result.importe
        if operaciones_sin_derecho_deduccion > Decimal("0")
        and result.direccion is not RegularizacionProrrataDireccion.NINGUNA
        else None
    )
    return ProrrataRegularizacionFeedProjection(
        result=result,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
        modelo_303_casilla_44_value=proposed_value,
        modelo_390_regularizacion_anual_value=proposed_value,
    )


def _binding_legal_refs(revision: ModeloRevision) -> tuple[LegalRefId, ...]:
    refs: list[LegalRefId] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for ref in getattr(binding, "legal_refs", ()):
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _binding_source_refs(revision: ModeloRevision) -> tuple[SourceRefId, ...]:
    refs: list[SourceRefId] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for ref in getattr(binding, "source_refs", ()):
            if ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _prorrata_bindings_by_output(revision: ModeloRevision) -> dict[str, BindingId]:
    bindings: dict[str, BindingId] = {}
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        output = getattr(binding.selector, "regularizacion_output", None)
        if isinstance(output, str):
            bindings[output] = binding.id
    return bindings


def _prorrata_declared_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    return tuple(sorted(binding.id for binding in revision.bindings if binding.source == _SOURCE_KIND))


def _prorrata_source_periods(revision: ModeloRevision) -> tuple[str, ...]:
    periods: list[str] = []
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        for period in getattr(binding.selector, "source_periods", ()):
            if period not in periods:
                periods.append(period)
    return tuple(periods or _SOURCE_PERIODS)


def _missing_current_year_casillas(current_year_values: Mapping[CasillaId, Decimal]) -> tuple[CasillaId, ...]:
    return tuple(casilla_id for casilla_id in _SOURCE_CASILLA_IDS if casilla_id not in current_year_values)


def _unresolved_binding_diagnostics(
    *,
    binding_ids: tuple[BindingId, ...],
    resolver_id: str,
    message: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        CalculationSourceDiagnostic(
            reason="unresolved_binding",
            source_kind=_SOURCE_KIND.value,
            resolver_id=resolver_id,
            binding_id=binding_id,
            message=message,
        )
        for binding_id in binding_ids
    )


def _current_year_values_provenance(
    *,
    context: CalculationSourceContext,
    snapshot: RegistrySnapshot,
    source_periods: tuple[str, ...] | None = None,
) -> CalculationSourceProvenance:
    periods = source_periods or _prorrata_source_periods(snapshot.revision)
    period_ref = ",".join(periods)
    return CalculationSourceProvenance(
        source_kind=_SOURCE_KIND.value,
        source_ref=f"{Modelo.M303.value}:{context.filing_year}:{period_ref}:prorrata-current-year-values",
        source_modelo=Modelo.M303.value,
        source_filing_year=context.filing_year,
        source_periods=periods,
        source_casilla_ids=_SOURCE_CASILLA_IDS,
        legal_refs=_binding_legal_refs(snapshot.revision),
        source_refs=_binding_source_refs(snapshot.revision),
    )


def _entry_for_register_provenance(
    register: ProrrataRegister,
    *,
    ejercicio: int,
) -> ProrrataRegisterEntry | None:
    entry = register.entry_for(ejercicio)
    if entry is not None:
        return entry
    entries = register.entries_for_ejercicio(ejercicio)
    return entries[0] if entries else None


def _register_provenance(
    *,
    context: CalculationSourceContext,
    entry: ProrrataRegisterEntry | None,
    provisional_resolution: ProrrataProvisionalResolution,
    snapshot: RegistrySnapshot,
) -> CalculationSourceProvenance:
    provenance = provisional_resolution.provenance
    provenance_token = provenance.value if provenance is not None else "resolved"
    suffix = provenance_token
    if entry is not None and entry.source_observation_ref is not None:
        suffix = f"{provenance_token}:{entry.source_observation_ref}"
    elif entry is not None and entry.authorisation_reference is not None:
        suffix = f"{provenance_token}:{entry.authorisation_reference}"
    return CalculationSourceProvenance(
        source_kind=_SOURCE_KIND.value,
        source_ref=f"prorrata-register:{context.filing_year}:{suffix}",
        source_filing_year=context.filing_year,
        legal_refs=_binding_legal_refs(snapshot.revision),
        source_refs=_binding_source_refs(snapshot.revision),
    )


def _prior_definitiva_provenance(
    *,
    carry: _PriorDefinitivaCarry,
    snapshot: RegistrySnapshot,
) -> CalculationSourceProvenance:
    return CalculationSourceProvenance(
        source_kind=_SOURCE_KIND.value,
        source_ref=f"{Modelo.M303.value}:{carry.source_filing_year}:{carry.source_period}:{_PORCENTAJE_ID}",
        source_modelo=Modelo.M303.value,
        source_filing_year=carry.source_filing_year,
        source_periods=(carry.source_period,),
        source_casilla_ids=(_PORCENTAJE_ID,),
        legal_refs=_binding_legal_refs(snapshot.revision),
        source_refs=_binding_source_refs(snapshot.revision),
    )


def _stamped_prior_year_definitiva(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
) -> _PriorDefinitivaCarry | None:
    prior_year = filing_year - 1
    candidates: list[tuple[int, object, _PriorDefinitivaCarry]] = []
    for payload in repository.iter_modelo(Modelo.M303.value):
        observation = payload.observation
        if observation.filing_year != prior_year or observation.period not in _SETTLEMENT_PERIOD_ORDER:
            continue
        percentage = observation.casilla_values.get(_PORCENTAJE_ID)
        if percentage is None:
            continue
        refused = revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        )
        if refused:
            continue
        candidates.append(
            (
                _SETTLEMENT_PERIOD_ORDER[observation.period],
                payload.captured_at,
                _PriorDefinitivaCarry(
                    percentage=percentage,
                    source_filing_year=observation.filing_year,
                    source_period=observation.period,
                ),
            )
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]


def _source_period_feed_from_observations(
    repository: CalculationObservationRepository,
    *,
    snapshot: RegistrySnapshot,
    filing_year: int,
) -> _CurrentYearSourcePeriodFeed:
    periods = _prorrata_source_periods(snapshot.revision)
    if not periods:
        return _CurrentYearSourcePeriodFeed(values={}, source_periods=())

    observed_by_period: dict[str, Mapping[CasillaId, Decimal]] = {}
    missing_periods: list[str] = []
    for period in periods:
        payload = repository.load_observation(Modelo.M303.value, Period.from_year_and_code(filing_year, period))
        if payload is None:
            missing_periods.append(period)
            continue
        observation = payload.observation
        refused = revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        )
        if refused:
            missing_periods.append(period)
            continue
        observed_by_period[period] = observation.casilla_values

    values: dict[CasillaId, Decimal] = {}
    regularised_periods = periods[:-1] if len(periods) > 1 else periods
    cuota_values = [
        period_values[_CUOTA_DEDUCIBLE_TOTAL_ID]
        for period in regularised_periods
        if (period_values := observed_by_period.get(period)) is not None
        and _CUOTA_DEDUCIBLE_TOTAL_ID in period_values
    ]
    if len(cuota_values) == len(regularised_periods):
        values[_CUOTA_DEDUCIBLE_TOTAL_ID] = sum(cuota_values, Decimal("0"))

    settlement_values = observed_by_period.get(periods[-1])
    if settlement_values is not None:
        for casilla_id in (_VOLUMEN_CON_DERECHO_ID, _VOLUMEN_TOTAL_ID, _PORCENTAJE_ID):
            value = settlement_values.get(casilla_id)
            if value is not None:
                values[casilla_id] = value

    return _CurrentYearSourcePeriodFeed(
        values=values,
        source_periods=periods,
        missing_source_periods=tuple(missing_periods),
    )


def _resolve_prorrata_regularizacion_binding_values(
    revision: ModeloRevision,
    *,
    current_year_values: Mapping[CasillaId, Decimal],
    provisional_percentage: Decimal,
) -> dict[BindingId, Decimal]:
    binding_by_output = _prorrata_bindings_by_output(revision)
    if not binding_by_output:
        return {}

    volumen_total = current_year_values[_VOLUMEN_TOTAL_ID]
    volumen_con_derecho = current_year_values[_VOLUMEN_CON_DERECHO_ID]
    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=current_year_values[_CUOTA_DEDUCIBLE_TOTAL_ID],
        prorrata_provisional_pct=provisional_percentage,
        prorrata_definitiva_pct=current_year_values[_PORCENTAJE_ID],
        operaciones_sin_derecho_deduccion=volumen_total - volumen_con_derecho,
    )
    values_by_output = {
        _OUTPUT_MODELO_303_CASILLA_44: projection.modelo_303_casilla_44_value or _ZERO,
        _OUTPUT_MODELO_390_REGULARIZACION_ANUAL: projection.modelo_390_regularizacion_anual_value or _ZERO,
    }
    return {
        binding_id: values_by_output[output]
        for output, binding_id in binding_by_output.items()
        if output in values_by_output
    }


def _modelo_303_target_inputs(
    revision: ModeloRevision,
    *,
    binding_values: Mapping[BindingId, Decimal],
    modelo: str,
) -> dict[CasillaId, Decimal]:
    if modelo != Modelo.M303.value:
        return {}
    binding_by_output = _prorrata_bindings_by_output(revision)
    binding_id = binding_by_output.get(_OUTPUT_MODELO_303_CASILLA_44)
    if binding_id is None or binding_id not in binding_values:
        return {}
    return {CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA: binding_values[binding_id]}


class ProrrataRegularizacionSourceResolver:
    """Resolve annual prorrata-general regularisation bindings from governed carries."""

    resolver_id = _SOURCE_KIND.value
    owned_sources: tuple[BindingSourceKind, ...] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        current_year_values: Mapping[CasillaId, Decimal] | None = None,
        missing_current_year_casilla_ids: Iterable[CasillaId] = (),
        unresolved_current_year_casilla_ids: Iterable[CasillaId] = (),
        prorrata_register_repository: ProrrataRegisterRepository | None = None,
        observation_repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
    ) -> None:
        self._current_year_values = dict(current_year_values or {})
        self._missing_current_year_casilla_ids = tuple(missing_current_year_casilla_ids)
        self._unresolved_current_year_casilla_ids = tuple(unresolved_current_year_casilla_ids)
        self._prorrata_register_repository = prorrata_register_repository
        self._observation_repository = observation_repository
        self._registry_snapshot = registry_snapshot

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        declared_binding_ids = _prorrata_declared_binding_ids(snapshot.revision)
        if not declared_binding_ids:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        observation_repository = self._observation_repository or CalculationObservationRepository()
        try:
            source_period_feed = _source_period_feed_from_observations(
                observation_repository,
                snapshot=snapshot,
                filing_year=context.filing_year,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        current_year_values = {
            **self._current_year_values,
            **dict(source_period_feed.values),
        }
        missing_current = tuple(
            dict.fromkeys(
                (
                    *_missing_current_year_casillas(current_year_values),
                    *(
                        casilla_id
                        for casilla_id in self._missing_current_year_casilla_ids
                        if casilla_id not in current_year_values
                    ),
                    *(
                        casilla_id
                        for casilla_id in self._unresolved_current_year_casilla_ids
                        if casilla_id not in current_year_values
                    ),
                )
            )
        )
        if missing_current:
            message = (
                f"prorrata_regularizacion binding requires current-year registry casillas "
                f"{tuple(str(casilla_id) for casilla_id in missing_current)} before it can resolve"
            )
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=declared_binding_ids,
                diagnostics=_unresolved_binding_diagnostics(
                    binding_ids=declared_binding_ids,
                    resolver_id=self.resolver_id,
                    message=message,
                ),
            )

        register_repository = self._prorrata_register_repository or ProrrataRegisterRepository(
            bucket_id=context.bucket_id,
        )
        try:
            register = register_repository.load()
            prior_definitiva = _stamped_prior_year_definitiva(
                observation_repository,
                filing_year=context.filing_year,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )

        current_provenance = _current_year_values_provenance(
            context=context,
            snapshot=snapshot,
            source_periods=source_period_feed.source_periods,
        )
        register_entries = register.entries_for_ejercicio(context.filing_year)
        applicability = derive_prorrata_applicability(
            register_entries=register_entries,
            declared_volume_total=current_year_values[_VOLUMEN_TOTAL_ID],
            declared_volume_con_derecho=current_year_values[_VOLUMEN_CON_DERECHO_ID],
        )
        if not applicability.applies:
            zero_values = {binding_id: _ZERO for binding_id in declared_binding_ids}
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                binding_values=zero_values,
                bound_inputs_by_casilla_id=_modelo_303_target_inputs(
                    snapshot.revision,
                    binding_values=zero_values,
                    modelo=context.modelo,
                ),
                provenance=(current_provenance,),
            )

        provisional = register.resolve_provisional(context.filing_year)
        provenance: tuple[CalculationSourceProvenance, ...]
        if provisional.resolved:
            register_entry = _entry_for_register_provenance(register, ejercicio=context.filing_year)
            provenance = (
                current_provenance,
                _register_provenance(
                    context=context,
                    entry=register_entry,
                    provisional_resolution=provisional,
                    snapshot=snapshot,
                ),
            )
            assert provisional.percentage is not None
            provisional_percentage = provisional.percentage
        elif prior_definitiva is not None:
            provenance = (
                current_provenance,
                _prior_definitiva_provenance(carry=prior_definitiva, snapshot=snapshot),
            )
            provisional_percentage = prior_definitiva.percentage
        else:
            message = (
                f"prorrata_regularizacion binding for {context.filing_year} requires a resolved provisional "
                "percentage from the prorrata register or a stamped prior-year Modelo 303 settlement observation"
            )
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=declared_binding_ids,
                diagnostics=_unresolved_binding_diagnostics(
                    binding_ids=declared_binding_ids,
                    resolver_id=self.resolver_id,
                    message=message,
                ),
                provenance=(current_provenance,),
            )

        binding_values = _resolve_prorrata_regularizacion_binding_values(
            snapshot.revision,
            current_year_values=current_year_values,
            provisional_percentage=provisional_percentage,
        )
        unresolved = tuple(binding_id for binding_id in declared_binding_ids if binding_id not in binding_values)
        diagnostics = _unresolved_binding_diagnostics(
            binding_ids=unresolved,
            resolver_id=self.resolver_id,
            message="prorrata_regularizacion binding selector did not map to a resolver output",
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_modelo_303_target_inputs(
                snapshot.revision,
                binding_values=binding_values,
                modelo=context.modelo,
            ),
            unresolved_binding_ids=unresolved,
            diagnostics=diagnostics,
            provenance=provenance,
        )


def build_prorrata_regularizacion_advisory(
    *,
    cuotas_soportadas_deducibles: Decimal,
    prorrata_provisional_pct: Decimal,
    prorrata_definitiva_pct: Decimal,
    operaciones_sin_derecho_deduccion: Decimal,
    regularizacion_year: int,
) -> tuple[RegularizacionProrrataResult, CalculationSourceDiagnostic | None]:
    """Compute the annual regularización and build the fallback advisory.

    Returns the pure :class:`RegularizacionProrrataResult` plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the taxpayer
    has exempt-without-right operations in the year (``operaciones_sin_derecho_
    deduccion > 0`` — prorrata applies) and the definitive percentage differs from
    the provisional one applied across the quarters (a regularización is due). In
    that case a taxpayer who leaves casilla 44 blank is alerted rather than
    silently under- or over-declaring. When prorrata does not apply, or the two
    percentages coincide, the diagnostic is ``None`` (nothing to regularise, no
    noise).

    The diagnostic ``message`` names the provisional and definitive percentages,
    the direction (deducción complementaria vs ingreso), and the proposed
    casilla-44 value.

    Args:
        cuotas_soportadas_deducibles: The year's total deductible input IVA
            (LIVA art. 105.Seis).
        prorrata_provisional_pct: Provisional deduction percentage applied during
            the year (LIVA art. 105.Uno — the prior-year definitive).
        prorrata_definitiva_pct: Definitive deduction percentage for the year
            (LIVA art. 104, computed from full-year volumes).
        operaciones_sin_derecho_deduccion: The year's exempt-without-right
            operation volume. When zero, prorrata does not apply and no
            regularización is proposed.
        regularizacion_year: The year being calculated (for the message).

    Returns:
        ``(result, diagnostic)`` where ``result`` is the
        :class:`RegularizacionProrrataResult`; the diagnostic is ``None`` when
        there is nothing to regularise.
    """
    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=cuotas_soportadas_deducibles,
        prorrata_provisional_pct=prorrata_provisional_pct,
        prorrata_definitiva_pct=prorrata_definitiva_pct,
        operaciones_sin_derecho_deduccion=operaciones_sin_derecho_deduccion,
    )
    result = projection.result
    if projection.modelo_303_casilla_44_value is None:
        return result, None

    sentido = "deducción complementaria" if result.direccion is RegularizacionProrrataDireccion.DEDUCCION else "ingreso"
    message = (
        f"Regularización de prorrata por porcentaje definitivo (LIVA arts. 104-105) "
        f"para {regularizacion_year}: prorrata provisional {prorrata_provisional_pct}% "
        f"→ definitiva {prorrata_definitiva_pct}% ({sentido}). "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA}: "
        f"{projection.modelo_303_casilla_44_value}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.PRORRATA_REGULARIZACION.value,
        message=message,
    )
    return result, diagnostic


__all__ = [
    "CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA",
    "ProrrataApplicabilityProjection",
    "ProrrataDeclaredVolumeLedgerRollup",
    "ProrrataRegularizacionFeedProjection",
    "ProrrataRegularizacionSourceResolver",
    "build_prorrata_declared_volume_divergence_advisory",
    "build_prorrata_missing_provisional_advisory",
    "build_prorrata_regularizacion_advisory",
    "derive_prorrata_applicability",
    "project_prorrata_regularizacion_feed",
]
