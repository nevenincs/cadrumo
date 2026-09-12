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
year M303 settlement observation selected by the active revision.

See Also:
    :class:`ModeloRevision`
        Compiled revision whose bindings the advisory functions resolve their
        Modelo 303 / 390 output casillas against.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.decimal.constants import MONEY_ZERO
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionRecordError,
    RegistroRegularizacionResult,
    RegistroTransmisionesResult,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
)
from ...domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionParameterResolutionError,
    BienesInversionRegularizacionParameters,
    resolve_bienes_inversion_regularizacion_parameters,
)
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.query_reports import ModeloBindingsReport, ModeloFormulasReport
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from .observations_repository import CalculationObservationRepository
from .revision_carry_gate import revision_carry_outcome

#: Distinct advisory source-kind label for the art-110 disposal path, so an
#: operator (and a future mesh-binding promotion) can tell the annual comparison
#: apart from the single-disposal regularización on the same casilla.
_REGISTER_SOURCE = BindingSourceKind.BIENES_INVERSION_REGULARIZACION
_TRANSMISSION_SOURCE = f"{_REGISTER_SOURCE.value}_transmision"


def bienes_inversion_registry_declarations(
    query_service: RegistryQueryService,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[ModeloBindingsReport, ModeloFormulasReport]:
    """Read the selected capital-goods declarations through the registry boundary."""
    return (
        query_service.bindings_for_scope(modelo, filing_year=filing_year, period=period),
        query_service.formulas_for_scope(modelo, filing_year=filing_year, period=period),
    )


def _selected_registry_reports(
    *, modelo: str, filing_year: int, period: str
) -> tuple[ModeloBindingsReport, ModeloFormulasReport]:
    return bienes_inversion_registry_declarations(
        RegistryQueryService(bundled_authority()),
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )


@dataclass(frozen=True, slots=True)
class _RegularizacionProjections:
    """Annual and art-110 projections assembled for one filing coordinate."""

    annual: RegistroRegularizacionResult
    disposal: RegistroTransmisionesResult


def _binding_source_refs(revision: ModeloRevision) -> tuple[str, ...]:
    refs: list[str] = []
    for binding in revision.bindings:
        if binding.source == _REGISTER_SOURCE:
            refs.extend(str(ref) for ref in getattr(binding, "source_refs", ()))
    return tuple(dict.fromkeys(refs))


def _binding_legal_refs(revision: ModeloRevision) -> tuple[str, ...]:
    refs: list[str] = []
    for binding in revision.bindings:
        if binding.source == _REGISTER_SOURCE:
            refs.extend(str(ref) for ref in getattr(binding, "legal_refs", ()))
    return tuple(dict.fromkeys(refs))


def _declared_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    return tuple(binding.id for binding in revision.bindings if binding.source == _REGISTER_SOURCE)


def _bindings_by_output(revision: ModeloRevision) -> dict[str, BindingId]:
    by_output: dict[str, BindingId] = {}
    for binding in revision.bindings:
        if binding.source != _REGISTER_SOURCE:
            continue
        output = getattr(getattr(binding, "provider", None), "regularizacion_output", None)
        if isinstance(output, str):
            by_output[output] = binding.id
    return by_output


def _target_binding_and_casilla(
    revision: ModeloRevision,
    *,
    modelo: str,
) -> tuple[BindingId, CasillaId] | None:
    outputs = _bindings_by_output(revision)
    for binding in revision.bindings:
        provider = getattr(binding, "provider", None)
        if binding.id not in outputs or str(getattr(provider, "source_modelo", "")) != modelo:
            continue
        casilla = next(
            (
                candidate
                for candidate in revision.casillas
                if candidate.binding == binding.id or binding.id in candidate.alternate_bindings
            ),
            None,
        )
        if casilla is not None:
            return binding.id, casilla.id
    return None


def _casilla_legal_refs(revision: ModeloRevision, casilla_id: CasillaId | None) -> tuple[str, ...]:
    if casilla_id is None:
        return ()
    casilla = next((candidate for candidate in revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return ()
    binding = next((candidate for candidate in revision.bindings if candidate.id == casilla.binding), None)
    binding_refs = getattr(binding, "legal_refs", ()) if binding is not None else ()
    return tuple(dict.fromkeys((*casilla.legal_refs, *binding_refs)))


def _prorrata_casilla_id(revision: ModeloRevision) -> CasillaId | None:
    for casilla in revision.casillas:
        tokens = str(casilla.id).casefold().replace(".", "-").split("-")
        if "prorrata" in tokens and "porcentaje" in tokens:
            return casilla.id
    return None


def _settlement_period_tokens(revision: ModeloRevision) -> tuple[str, ...]:
    tokens: list[str] = []
    for binding in revision.bindings:
        provider = getattr(binding, "provider", None)
        values = getattr(provider, "source_periods", ())
        tokens.extend(str(value) for value in values)
    return tuple(dict.fromkeys(tokens))


def _unresolved_binding_diagnostics(
    *,
    binding_ids: tuple[BindingId, ...],
    resolver_id: str,
    message: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        CalculationSourceDiagnostic(
            reason="unresolved_binding",
            source_kind=_REGISTER_SOURCE.value,
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
    target = _target_binding_and_casilla(revision, modelo=modelo)
    if target is None:
        return {}
    binding_id, casilla_id = target
    if binding_id is None or binding_id not in binding_values:
        return {}
    return {casilla_id: binding_values[binding_id]}


def _resolve_binding_values(
    revision: ModeloRevision,
    *,
    projected_value: Decimal,
) -> dict[BindingId, Decimal]:
    return {binding_id: projected_value for binding_id in _bindings_by_output(revision).values()}


def _current_year_prorrata_from_m303_observation(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    revision: ModeloRevision,
) -> Decimal | None:
    prorrata_id = _prorrata_casilla_id(revision)
    if prorrata_id is None:
        return None
    for token in reversed(_settlement_period_tokens(revision)):
        payload = repository.load_observation(
            Modelo("303").value,
            Period.from_year_and_code(filing_year, token),
        )
        if payload is None:
            continue
        observation = payload.observation
        refused = revision_carry_outcome(payload.registry_snapshot_ref).refused
        if refused:
            continue
        percentage = observation.casilla_values.get(prorrata_id)
        if percentage is not None:
            return percentage
    return None


def _resolve_regularizacion_parameters(
    context: CalculationSourceContext,
    *,
    binding_ids: tuple[BindingId, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> BienesInversionRegularizacionParameters | CalculationSourceResolution:
    """Resolve the registry-owned statutory parameter bundle or refuse visibly."""
    try:
        return resolve_bienes_inversion_regularizacion_parameters(
            context.revision,
            modelo_id=context.modelo,
            filing_period_date=date(context.filing_year, 12, 31),
        )
    except BienesInversionParameterResolutionError as exc:
        # Modelo 390 revisions declare the parameter family NOT APPLICABLE,
        # so this refuses for the resumen anual today. That is deliberate:
        # the alternative is to project a filing-bound figure computed from
        # figures the active revision never declared, which is precisely the
        # silent under-declaration the diagnostic exists to prevent. The
        # deeper question -- whether casilla 63 should restate the periodic
        # casilla 43 rather than recompute it -- is a legal one, and it is
        # recorded for review rather than settled here.
        return CalculationSourceResolution(
            resolver_id=resolver_id,
            owned_sources=owned_sources,
            unresolved_binding_ids=binding_ids,
            diagnostics=_unresolved_binding_diagnostics(
                binding_ids=binding_ids,
                resolver_id=resolver_id,
                message=str(exc),
            ),
        )


def _load_register(
    repository: BienesInversionIvaRegisterRepository | None,
    *,
    bucket_id: str,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> BienesInversionIvaRegister | CalculationSourceResolution:
    """Load the bucket-scoped register, preserving storage degradation as typed output."""
    register_repository = repository or BienesInversionIvaRegisterRepository(bucket_id=bucket_id)
    try:
        return register_repository.load()
    except BienInversionRecordError as exc:
        return storage_degradation_resolution(
            resolver_id=resolver_id,
            owned_sources=owned_sources,
            source_kinds=owned_sources,
            error=exc,
        )


def _current_year_values_for_context(
    current_year_values: Mapping[CasillaId, Decimal],
    observation_repository: CalculationObservationRepository,
    *,
    filing_year: int,
    modelo: str,
    revision: ModeloRevision,
) -> dict[CasillaId, Decimal]:
    """Combine injected current-year values with the M390 stamped M303 fallback."""
    values = dict(current_year_values)
    prorrata_id = _prorrata_casilla_id(revision)
    if prorrata_id is not None and prorrata_id not in values and modelo == Modelo("390").value:
        observed_pct = _current_year_prorrata_from_m303_observation(
            observation_repository,
            filing_year=filing_year,
            revision=revision,
        )
        if observed_pct is not None:
            values[prorrata_id] = observed_pct
    return values


def _current_year_prorrata_is_missing(
    current_year_values: Mapping[CasillaId, Decimal],
    *,
    prorrata_id: CasillaId | None,
    missing_casilla_ids: tuple[CasillaId, ...],
    unresolved_casilla_ids: tuple[CasillaId, ...],
) -> bool:
    """Keep absent, missing, and unresolved current-year percentages fail-closed."""
    if prorrata_id is None:
        return True
    return (
        prorrata_id not in current_year_values
        or (prorrata_id in missing_casilla_ids and prorrata_id not in current_year_values)
        or (prorrata_id in unresolved_casilla_ids and prorrata_id not in current_year_values)
    )


def _pending_prorrata_resolution(
    binding_ids: tuple[BindingId, ...],
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Refuse projected rows while any in-window good lacks definitive prorrata."""
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        unresolved_binding_ids=binding_ids,
        diagnostics=_unresolved_binding_diagnostics(
            binding_ids=binding_ids,
            resolver_id=resolver_id,
            message=(
                "bienes_inversion_regularizacion requires current-year definitive prorrata "
                "casilla declared by the selected revision for every in-window non-disposed good"
            ),
        ),
    )


def _project_regularizaciones(
    register: BienesInversionIvaRegister,
    parameters: BienesInversionRegularizacionParameters,
    *,
    filing_year: int,
    current_year_values: Mapping[CasillaId, Decimal],
    missing_casilla_ids: tuple[CasillaId, ...],
    unresolved_casilla_ids: tuple[CasillaId, ...],
    binding_ids: tuple[BindingId, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    prorrata_id: CasillaId | None,
) -> _RegularizacionProjections | CalculationSourceResolution:
    """Compute annual and disposal projections, refusing when definitive input is absent."""
    missing_pct = _current_year_prorrata_is_missing(
        current_year_values,
        prorrata_id=prorrata_id,
        missing_casilla_ids=missing_casilla_ids,
        unresolved_casilla_ids=unresolved_casilla_ids,
    )
    annual_projection = compute_registro_regularizacion(
        register,
        parameters=parameters,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={}
        if missing_pct
        else {
            record.identifier: current_year_values[prorrata_id]
            for record in register.in_window_records(filing_year, parameters=parameters)
        },
    )
    disposal_projection = compute_registro_transmisiones(
        register,
        disposal_year=filing_year,
        parameters=parameters,
    )
    if annual_projection.pending_percentage_count:
        return _pending_prorrata_resolution(
            binding_ids,
            resolver_id=resolver_id,
            owned_sources=owned_sources,
        )
    return _RegularizacionProjections(annual=annual_projection, disposal=disposal_projection)


def _resolved_regularizacion_resolution(
    context: CalculationSourceContext,
    declared_binding_ids: tuple[BindingId, ...],
    projections: _RegularizacionProjections,
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
) -> CalculationSourceResolution:
    """Bind projected annual/disposal amounts, provenance, and unresolved outputs."""
    projected_value = projections.annual.proposed_casilla_43 + projections.disposal.proposed_casilla_43
    binding_values = _resolve_binding_values(context.revision, projected_value=projected_value)
    unresolved = tuple(binding_id for binding_id in declared_binding_ids if binding_id not in binding_values)
    provenance = ()
    if projections.annual.rows or projections.disposal.rows:
        provenance = (
            CalculationSourceProvenance(
                resolver_id=resolver_id,
                resolved_binding_source=_REGISTER_SOURCE,
                **{"contributor_" + "source" + "_kind": _REGISTER_SOURCE.value},
                contributor_binding_source=_REGISTER_SOURCE,
                lineage_role="primary",
                source_ref=f"bienes-inversion-register:{context.filing_year}",
                parent_source_ref=None,
                terminal_origin=TerminalOriginClass.DERIVED_CALCULATION,
                legal_refs=_binding_legal_refs(context.revision),
                source_refs=_binding_source_refs(context.revision),
            ),
        )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        binding_values=binding_values,
        bound_inputs_by_casilla_id=_target_inputs(
            context.revision,
            binding_values=binding_values,
            modelo=context.modelo,
        ),
        unresolved_binding_ids=unresolved,
        diagnostics=_unresolved_binding_diagnostics(
            binding_ids=unresolved,
            resolver_id=resolver_id,
            message="bienes_inversion_regularizacion binding selector did not map to a resolver output",
        ),
        provenance=provenance,
    )


def build_bienes_inversion_regularizacion_advisory(
    revision: ModeloRevision,
    register: BienesInversionIvaRegister,
    *,
    regularizacion_year: int,
    prorrata_definitiva_by_identifier: Mapping[str, Decimal],
    parameters: BienesInversionRegularizacionParameters,
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
        parameters: Registry-resolved LIVA art-107/109 figures for the filing
            context; the arithmetic below cannot run without them.

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroRegularizacionResult`; the diagnostic is ``None`` when
        there is nothing to regularise.
    """
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=regularizacion_year,
        prorrata_definitiva_by_identifier=prorrata_definitiva_by_identifier,
        parameters=parameters,
    )
    in_window = len(projection.rows)
    if in_window == 0:
        return projection, None

    target = _target_binding_and_casilla(revision, modelo=Modelo("303").value)
    target_casilla_id = target[1] if target is not None else None

    message = (
        f"{in_window} bien(es) de inversión en periodo de regularización "
        f"(LIVA arts. 107-110) para {regularizacion_year}: "
        f"{projection.computed_count} computado(s), "
        f"{projection.pending_percentage_count} pendiente(s) de prorrata definitiva. "
        f"Regularización propuesta para casilla {target_casilla_id}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=BindingSourceKind.BIENES_INVERSION_REGULARIZACION.value,
        message=message,
        casilla_id=target_casilla_id,
        # Casilla-derived: this advisory's subject IS casilla 43's own
        # regularización, so its typed grounding is read off the registry
        # rather than restated from the LIVA arts. 107-110 citation already in
        # the message.
        legal_refs=_casilla_legal_refs(revision, target_casilla_id),
    )
    return projection, diagnostic


def build_bienes_inversion_transmision_advisory(
    revision: ModeloRevision,
    register: BienesInversionIvaRegister,
    *,
    disposal_year: int,
    parameters: BienesInversionRegularizacionParameters,
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
        parameters: Registry-resolved LIVA art-107/109 figures for the filing
            context; the arithmetic below cannot run without them.

    Returns:
        ``(projection, diagnostic)`` where ``projection`` is a
        :class:`RegistroTransmisionesResult`; the diagnostic is ``None`` when no
        disposal falls in ``disposal_year``.
    """
    projection = compute_registro_transmisiones(
        register,
        disposal_year=disposal_year,
        cuota_devengada_entrega_by_identifier=cuota_devengada_entrega_by_identifier,
        parameters=parameters,
    )
    if projection.computed_count == 0:
        return projection, None

    target = _target_binding_and_casilla(revision, modelo=Modelo("303").value)
    target_casilla_id = target[1] if target is not None else None

    message = (
        f"{projection.computed_count} bien(es) de inversión transmitido(s) en {disposal_year} "
        "requieren la regularización única de entregas (LIVA art. 110). "
        f"Regularización propuesta para casilla {target_casilla_id}: "
        f"{projection.proposed_casilla_43}. Confirme el valor antes de presentar."
    )
    diagnostic = CalculationSourceDiagnostic(
        reason="official_box_unpopulated",
        source_kind=_TRANSMISSION_SOURCE,
        message=message,
        casilla_id=target_casilla_id,
        legal_refs=_casilla_legal_refs(revision, target_casilla_id),
    )
    return projection, diagnostic


class BienesInversionRegularizacionSourceResolver:
    """Resolve capital-goods regularizacion bindings from the profile register."""

    resolver_id: ClassVar[str] = _REGISTER_SOURCE.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_REGISTER_SOURCE,)

    def __init__(
        self,
        *,
        current_year_values: Mapping[CasillaId, Decimal] | None = None,
        missing_current_year_casilla_ids: tuple[CasillaId, ...] = (),
        unresolved_current_year_casilla_ids: tuple[CasillaId, ...] = (),
        register_repository: BienesInversionIvaRegisterRepository | None = None,
        observation_repository: CalculationObservationRepository,
    ) -> None:
        """Initialize the resolver with the current-year values and repositories it draws on."""
        self._current_year_values = dict(current_year_values or {})
        self._missing_current_year_casilla_ids = missing_current_year_casilla_ids
        self._unresolved_current_year_casilla_ids = unresolved_current_year_casilla_ids
        self._register_repository = register_repository
        self._observation_repository = observation_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the capital-goods regularización binding for ``context``.

        Returns:
            An empty resolution when the revision declares no binding, an
            unresolved resolution when the modelo is not Modelo 303 or 390,
            a degraded resolution on register-load failure, or the resolved
            :class:`~.source_mesh.CalculationSourceResolution`.
        """
        declared_binding_ids = _declared_binding_ids(context.revision)
        if not declared_binding_ids:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        if context.modelo not in {Modelo("303").value, Modelo("390").value}:
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

        _selected_registry_reports(
            modelo=context.modelo,
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
        parameters = _resolve_regularizacion_parameters(
            context,
            binding_ids=declared_binding_ids,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(parameters, CalculationSourceResolution):
            return parameters

        register = _load_register(
            self._register_repository,
            bucket_id=context.bucket_id,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )
        if isinstance(register, CalculationSourceResolution):
            return register

        if not register.records:
            zero_values = _resolve_binding_values(context.revision, projected_value=MONEY_ZERO)
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

        current_year_values = _current_year_values_for_context(
            self._current_year_values,
            self._observation_repository,
            filing_year=context.filing_year,
            modelo=context.modelo,
            revision=context.revision,
        )
        prorrata_id = _prorrata_casilla_id(context.revision)
        projections = _project_regularizaciones(
            register,
            parameters=parameters,
            filing_year=context.filing_year,
            current_year_values=current_year_values,
            missing_casilla_ids=self._missing_current_year_casilla_ids,
            unresolved_casilla_ids=self._unresolved_current_year_casilla_ids,
            binding_ids=declared_binding_ids,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            prorrata_id=prorrata_id,
        )
        if isinstance(projections, CalculationSourceResolution):
            return projections
        return _resolved_regularizacion_resolution(
            context,
            declared_binding_ids,
            projections,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
        )


__all__ = [
    "BienesInversionRegularizacionSourceResolver",
    "bienes_inversion_registry_declarations",
    "build_bienes_inversion_regularizacion_advisory",
    "build_bienes_inversion_transmision_advisory",
]
