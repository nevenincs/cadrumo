"""Advisory projection for the capital-goods IVA regularización (LIVA arts. 107-110).

Builds the non-blocking source diagnostics the calculate path surfaces for
Modelo 303 casilla 43 / Modelo 390 casilla 63: the ordinary annual
art-109 comparison for in-window, non-disposed goods
(:func:`build_bienes_inversion_regularizacion_advisory`), and the art-110 single
("única") disposal regularización for a good disposed of during the filing year
(:func:`build_bienes_inversion_transmision_advisory`). The source resolver
projects the same register-backed amount into the governed M303/M390 binding
targets when the current-year definitive prorrata percentage is available; the
advisory functions remain as the visible fallback for operator review.

The pure projections never derive the definitive percentage. M303 supplies it
from the registry materialisation seam, while M390 may read the stamped current
year M303 settlement observation that already owns ``iva.prorrata-porcentaje``.

See Also:
    :class:`ModeloRevision`
        Compiled revision whose bindings the advisory functions resolve their
        Modelo 303 / 390 output casillas against.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import ClassVar

from ...core import BindingSourceKind, CalculationSourceLineageRole, CasillaId, Modelo, Period
from ...domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionRecordError,
    RegistroRegularizacionResult,
    RegistroTransmisionesResult,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva import m303_annual_settlement_period_tokens
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    casilla_registry_legal_refs,
    storage_degradation_resolution,
)
from ..bienes_inversion import BienesInversionIvaRegisterRepository
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

#: The Modelo 303 casilla the register feeds. Deducciones block, "Regularización
#: de bienes de inversión" (LIVA arts. 107-110).
CASILLA_REGULARIZACION_BIENES_INVERSION = "43"
CASILLA_M390_REGULARIZACION_BIENES_INVERSION: CasillaId = "iva.anual.regularizacion-bienes-inversion"
_SOURCE_KIND = BindingSourceKind.BIENES_INVERSION_REGULARIZACION
_OUTPUT_MODELO_303_CASILLA_43 = "modelo_303_casilla_43"
_OUTPUT_MODELO_390_CASILLA_63 = "modelo_390_casilla_63"
_CURRENT_YEAR_PRORRATA_ID: CasillaId = "iva.prorrata-porcentaje"
_ZERO = Decimal("0.00")

#: Distinct advisory source-kind label for the art-110 disposal path, so an
#: operator (and a future mesh-binding promotion) can tell the annual comparison
#: apart from the single-disposal regularización on the same casilla.
_TRANSMISION_SOURCE_KIND = f"{BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value}_transmision"


def _binding_source_refs(revision: ModeloRevision) -> tuple[str, ...]:
    refs: list[str] = []
    for binding in revision.bindings:
        if binding.source == _SOURCE_KIND:
            refs.extend(str(ref) for ref in getattr(binding, "source_refs", ()))
    return tuple(dict.fromkeys(refs))


def _declared_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    return tuple(binding.id for binding in revision.bindings if binding.source == _SOURCE_KIND)


def _bindings_by_output(revision: ModeloRevision) -> dict[str, BindingId]:
    by_output: dict[str, BindingId] = {}
    for binding in revision.bindings:
        if binding.source != _SOURCE_KIND:
            continue
        selector = binding.selector
        output = None
        if isinstance(selector, Mapping):
            output = selector.get("regularizacion_output")
        else:
            output = getattr(selector, "regularizacion_output", None)
        if isinstance(output, str):
            by_output[output] = binding.id
    return by_output


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
            binding_id=binding_id,
            resolver_id=resolver_id,
            message=message,
        )
        for binding_id in binding_ids
    )


def _target_inputs(
    revision: ModeloRevision,
    *,
    binding_values: Mapping[BindingId, Decimal],
    modelo: str,
) -> dict[CasillaId, Decimal]:
    if modelo == Modelo.M303.value:
        binding_id = _bindings_by_output(revision).get(_OUTPUT_MODELO_303_CASILLA_43)
        casilla_id = CASILLA_REGULARIZACION_BIENES_INVERSION
    elif modelo == Modelo.M390.value:
        binding_id = _bindings_by_output(revision).get(_OUTPUT_MODELO_390_CASILLA_63)
        casilla_id = CASILLA_M390_REGULARIZACION_BIENES_INVERSION
    else:
        return {}
    if binding_id is None or binding_id not in binding_values:
        return {}
    return {casilla_id: binding_values[binding_id]}


def _resolve_binding_values(
    revision: ModeloRevision,
    *,
    projected_value: Decimal,
) -> dict[BindingId, Decimal]:
    return {
        binding_id: projected_value
        for output, binding_id in _bindings_by_output(revision).items()
        if output in {_OUTPUT_MODELO_303_CASILLA_43, _OUTPUT_MODELO_390_CASILLA_63}
    }


def _current_year_prorrata_from_m303_observation(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
) -> Decimal | None:
    for token in reversed(m303_annual_settlement_period_tokens()):
        payload = repository.load_observation(
            Modelo.M303.value,
            Period.from_year_and_code(filing_year, token),
        )
        if payload is None:
            continue
        observation = payload.observation
        refused = revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        ).refused
        if refused:
            continue
        percentage = observation.casilla_values.get(_CURRENT_YEAR_PRORRATA_ID)
        if percentage is not None:
            return percentage
    return None


def build_bienes_inversion_regularizacion_advisory(
    revision: ModeloRevision,
    register: BienesInversionIvaRegister,
    *,
    regularizacion_year: int,
    prorrata_definitiva_by_identifier: Mapping[str, Decimal],
) -> tuple[RegistroRegularizacionResult, CalculationSourceDiagnostic | None]:
    """Project the register and build the fallback advisory diagnostic.

    Returns the register projection plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the register
    holds in-window, art-108-eligible, non-disposed goods for
    ``regularizacion_year`` — so a taxpayer who owns capital goods in their
    regularisation window is alerted that casilla 43 may be due, rather than
    silently filing zero. When no in-window goods exist the diagnostic is
    ``None`` (nothing to regularise, no noise). A good disposed of at or before
    ``regularizacion_year`` is excluded here and routed instead through
    :func:`build_bienes_inversion_transmision_advisory`.

    The diagnostic ``message`` names the in-window count, the number of goods whose
    regularización could be computed (a definitive percentage was supplied), the
    number still pending a definitive percentage, and the proposed casilla-43 value.

    Args:
        revision: The :class:`ModeloRevision` being calculated, read only for
            casilla 43's own registry grounding -- the caller of this function
            is M303-gated, so the Modelo 303 casilla constant is the correct
            one regardless of which revision year is loaded.
        register: The persisted :class:`BienesInversionIvaRegister`.
        regularizacion_year: The year being calculated.
        prorrata_definitiva_by_identifier: Current-year definitive deduction
            percentages keyed by record identifier (absent keys are pending).

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroRegularizacionResult`; the diagnostic is ``None`` when
        there is nothing to regularise.
    """
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=regularizacion_year,
        prorrata_definitiva_by_identifier=prorrata_definitiva_by_identifier,
    )
    in_window = len(projection.rows)
    if in_window == 0:
        return projection, None

    message = (
        f"{in_window} bien(es) de inversión en periodo de regularización "
        f"(LIVA arts. 107-110) para {regularizacion_year}: "
        f"{projection.computed_count} computado(s), "
        f"{projection.pending_percentage_count} pendiente(s) de prorrata definitiva. "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_BIENES_INVERSION}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value,
        message=message,
        casilla_id=CASILLA_REGULARIZACION_BIENES_INVERSION,
        # Casilla-derived: this advisory's subject IS casilla 43's own
        # regularización, so its typed grounding is read off the registry
        # rather than restated from the LIVA arts. 107-110 citation already in
        # the message.
        legal_refs=casilla_registry_legal_refs(revision, CASILLA_REGULARIZACION_BIENES_INVERSION),
    )
    return projection, diagnostic


def build_bienes_inversion_transmision_advisory(
    revision: ModeloRevision,
    register: BienesInversionIvaRegister,
    *,
    disposal_year: int,
    cuota_devengada_entrega_by_identifier: Mapping[str, Decimal] | None = None,
) -> tuple[RegistroTransmisionesResult, CalculationSourceDiagnostic | None]:
    """Project the register's art-110 disposals and build the advisory diagnostic.

    Returns the register-wide transmisión projection plus a non-blocking
    :class:`~application.aggregation.CalculationSourceDiagnostic` when the register
    holds a good disposed of in ``disposal_year`` with window time remaining — so
    a taxpayer who sold, transmitted, or otherwise disposed of a tracked capital
    good is alerted that the art-110 single regularización is due on casilla 43,
    rather than silently filing zero. Unlike the annual advisory, this projection
    carries no pending state: every fact art-110 needs (acquisition-year
    percentage, cuota soportada, disposal regime) is already on the record, so the
    diagnostic always names a concrete proposed figure (the regla-1ª cap is
    applied only when the caller supplies the disposal's own cuota devengada).

    Args:
        revision: The :class:`ModeloRevision` being calculated, read only for
            casilla 43's own registry grounding -- the caller of this function
            is M303-gated, so the Modelo 303 casilla constant is the correct
            one regardless of which revision year is loaded.
        register: The persisted :class:`BienesInversionIvaRegister`.
        disposal_year: The filing year being calculated.
        cuota_devengada_entrega_by_identifier: Optional per-good cuota devengada on
            the disposal itself, applied as the regla-1ª cap. Absent keys leave
            regla 1ª uncapped for that good.

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroTransmisionesResult`; the diagnostic is ``None`` when no
        disposal falls in ``disposal_year``.
    """
    projection = compute_registro_transmisiones(
        register,
        disposal_year=disposal_year,
        cuota_devengada_entrega_by_identifier=cuota_devengada_entrega_by_identifier,
    )
    if projection.computed_count == 0:
        return projection, None

    message = (
        f"{projection.computed_count} bien(es) de inversión transmitido(s) en {disposal_year} "
        "requieren la regularización única de entregas (LIVA art. 110). "
        f"Regularización propuesta para casilla {CASILLA_REGULARIZACION_BIENES_INVERSION}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=_TRANSMISION_SOURCE_KIND,
        message=message,
        casilla_id=CASILLA_REGULARIZACION_BIENES_INVERSION,
        legal_refs=casilla_registry_legal_refs(revision, CASILLA_REGULARIZACION_BIENES_INVERSION),
    )
    return projection, diagnostic


class BienesInversionRegularizacionSourceResolver:
    """Resolve capital-goods regularizacion bindings from the profile register."""

    resolver_id: ClassVar[str] = _SOURCE_KIND.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        current_year_values: Mapping[CasillaId, Decimal] | None = None,
        missing_current_year_casilla_ids: tuple[CasillaId, ...] = (),
        unresolved_current_year_casilla_ids: tuple[CasillaId, ...] = (),
        register_repository: BienesInversionIvaRegisterRepository | None = None,
        observation_repository: CalculationObservationRepository,
    ) -> None:
        self._current_year_values = dict(current_year_values or {})
        self._missing_current_year_casilla_ids = missing_current_year_casilla_ids
        self._unresolved_current_year_casilla_ids = unresolved_current_year_casilla_ids
        self._register_repository = register_repository
        self._observation_repository = observation_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        declared_binding_ids = _declared_binding_ids(context.revision)
        if not declared_binding_ids:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        if context.modelo not in {Modelo.M303.value, Modelo.M390.value}:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=declared_binding_ids,
                diagnostics=_unresolved_binding_diagnostics(
                    binding_ids=declared_binding_ids,
                    resolver_id=self.resolver_id,
                    message=(
                        "bienes_inversion_regularizacion declares only the Modelo 303 casilla 43 "
                        "and Modelo 390 casilla 63 targets"
                    ),
                ),
            )

        repository = self._register_repository or BienesInversionIvaRegisterRepository(bucket_id=context.bucket_id)
        try:
            register = repository.load()
        except BienInversionRecordError as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )

        if not register.records:
            zero_values = _resolve_binding_values(context.revision, projected_value=_ZERO)
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                binding_values=zero_values,
                bound_inputs_by_casilla_id=_target_inputs(
                    context.revision,
                    binding_values=zero_values,
                    modelo=context.modelo,
                ),
            )

        current_year_values = dict(self._current_year_values)
        if _CURRENT_YEAR_PRORRATA_ID not in current_year_values and context.modelo == Modelo.M390.value:
            observed_pct = _current_year_prorrata_from_m303_observation(
                self._observation_repository,
                filing_year=context.filing_year,
            )
            if observed_pct is not None:
                current_year_values[_CURRENT_YEAR_PRORRATA_ID] = observed_pct

        missing_pct = (
            _CURRENT_YEAR_PRORRATA_ID not in current_year_values
            or (
                _CURRENT_YEAR_PRORRATA_ID in self._missing_current_year_casilla_ids
                and _CURRENT_YEAR_PRORRATA_ID not in current_year_values
            )
            or (
                _CURRENT_YEAR_PRORRATA_ID in self._unresolved_current_year_casilla_ids
                and _CURRENT_YEAR_PRORRATA_ID not in current_year_values
            )
        )
        annual_projection = compute_registro_regularizacion(
            register,
            regularizacion_year=context.filing_year,
            prorrata_definitiva_by_identifier={}
            if missing_pct
            else {
                record.identifier: current_year_values[_CURRENT_YEAR_PRORRATA_ID]
                for record in register.in_window_records(context.filing_year)
            },
        )
        disposal_projection = compute_registro_transmisiones(register, disposal_year=context.filing_year)
        if annual_projection.pending_percentage_count:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                unresolved_binding_ids=declared_binding_ids,
                diagnostics=_unresolved_binding_diagnostics(
                    binding_ids=declared_binding_ids,
                    resolver_id=self.resolver_id,
                    message=(
                        "bienes_inversion_regularizacion requires current-year definitive prorrata "
                        "casilla 'iva.prorrata-porcentaje' for every in-window non-disposed good"
                    ),
                ),
            )

        projected_value = annual_projection.proposed_casilla_43 + disposal_projection.proposed_casilla_43
        binding_values = _resolve_binding_values(context.revision, projected_value=projected_value)
        unresolved = tuple(binding_id for binding_id in declared_binding_ids if binding_id not in binding_values)
        provenance = ()
        if annual_projection.rows or disposal_projection.rows:
            provenance = (
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=_SOURCE_KIND,
                    contributor_source_kind=_SOURCE_KIND.value,
                    contributor_binding_source=_SOURCE_KIND,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"bienes-inversion-register:{context.filing_year}",
                    parent_source_ref=None,
                    legal_refs=(
                        "ley-37-1992:art-107",
                        "ley-37-1992:art-108",
                        "ley-37-1992:art-109",
                        "ley-37-1992:art-110",
                    ),
                    source_refs=_binding_source_refs(context.revision),
                ),
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            bound_inputs_by_casilla_id=_target_inputs(
                context.revision,
                binding_values=binding_values,
                modelo=context.modelo,
            ),
            unresolved_binding_ids=unresolved,
            diagnostics=_unresolved_binding_diagnostics(
                binding_ids=unresolved,
                resolver_id=self.resolver_id,
                message="bienes_inversion_regularizacion binding selector did not map to a resolver output",
            ),
            provenance=provenance,
        )


__all__ = [
    "CASILLA_M390_REGULARIZACION_BIENES_INVERSION",
    "CASILLA_REGULARIZACION_BIENES_INVERSION",
    "BienesInversionRegularizacionSourceResolver",
    "build_bienes_inversion_regularizacion_advisory",
    "build_bienes_inversion_transmision_advisory",
]
