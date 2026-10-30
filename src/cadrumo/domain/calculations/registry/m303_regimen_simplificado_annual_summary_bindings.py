"""Modelo 303/4T to Modelo 390 simplified-regime annual-summary bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import FilingPeriodCode, StandardPeriodCode
from .binding_selector_utils import provider_member
from .binding_targets import bound_casilla_binding_ids
from .binding_temporal import BindingTemporalSelector, FiledCurrentPeriod
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, SourceRefId
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "M390_SUMMARY_ACTIVOS_FIJOS_DEVENGADA",
    "M390_SUMMARY_AGRICULTURAL_RESULT",
    "M390_SUMMARY_AIC_DEVENGADA",
    "M390_SUMMARY_DEVENGADA_TOTAL",
    "M390_SUMMARY_ISP_DEVENGADA",
    "M390_SUMMARY_NON_AGRICULTURAL_RESULT",
    "M390_SUMMARY_REGULARIZACION",
    "M390_SUMMARY_RESULTADO",
    "M390_SUMMARY_SOPORTADO_ACTIVOS_FIJOS",
    "M390_SUMMARY_SOURCE_READ_ENDPOINTS",
    "M390_SUMMARY_SUMA_DEDUCCIONES",
    "M303RegimenSimplificadoAnnualSummaryProvider",
    "M303RegimenSimplificadoAnnualSummaryRequirement",
    "m303_regimen_simplificado_annual_summary_requirement",
    "validate_m303_regimen_simplificado_annual_summary_revision",
]

#: The annual boxes the summary fills, by registry casilla id. A revision that
#: declares other endpoints no longer matches the assembler and is refused.
M390_SUMMARY_NON_AGRICULTURAL_RESULT: CasillaId = "iva.anual.regimen-simplificado.cuota-resultante-no-agricola"
M390_SUMMARY_AGRICULTURAL_RESULT: CasillaId = "iva.anual.regimen-simplificado.cuota-resultante-agricola"
M390_SUMMARY_AIC_DEVENGADA: CasillaId = "iva.anual.regimen-simplificado.aic-bienes-cuota-devengada"
M390_SUMMARY_ISP_DEVENGADA: CasillaId = "iva.anual.regimen-simplificado.inversion-sujeto-pasivo"
M390_SUMMARY_ACTIVOS_FIJOS_DEVENGADA: CasillaId = "iva.anual.regimen-simplificado.entrega-activos-fijos"
M390_SUMMARY_DEVENGADA_TOTAL: CasillaId = "iva.anual.reconciliacion.devengada-simplificado-303"
M390_SUMMARY_SOPORTADO_ACTIVOS_FIJOS: CasillaId = "iva.anual.regimen-simplificado.iva-soportado-activos-fijos"
M390_SUMMARY_REGULARIZACION: CasillaId = "iva.anual.regimen-simplificado.regularizacion-bienes-inversion"
M390_SUMMARY_SUMA_DEDUCCIONES: CasillaId = "iva.anual.regimen-simplificado.suma-deducciones"
M390_SUMMARY_RESULTADO: CasillaId = "iva.anual.regimen-simplificado.resultado"
#: The endpoints that copy one source box, in the order ``source_casilla_ids`` names them.
M390_SUMMARY_SOURCE_READ_ENDPOINTS: tuple[CasillaId, ...] = (
    M390_SUMMARY_AIC_DEVENGADA,
    M390_SUMMARY_ISP_DEVENGADA,
    M390_SUMMARY_ACTIVOS_FIJOS_DEVENGADA,
    M390_SUMMARY_DEVENGADA_TOTAL,
    M390_SUMMARY_SOPORTADO_ACTIVOS_FIJOS,
    M390_SUMMARY_REGULARIZACION,
    M390_SUMMARY_SUMA_DEDUCCIONES,
    M390_SUMMARY_RESULTADO,
)


class M303RegimenSimplificadoAnnualSummaryProvider(BaseModel):
    """Strict selector for one immutable Modelo 303 4T annual-summary endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY] = (
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )

    source_modelo: ModeloId
    temporal: BindingTemporalSelector = FiledCurrentPeriod(source_period=StandardPeriodCode.Q4.value)
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    summary_casilla_id: CasillaId

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _temporal_is_the_filed_fourth_quarter(self) -> M303RegimenSimplificadoAnnualSummaryProvider:
        """Pin the source window to the already-filed last quarter of the target's own year.

        The annual summary is legally the last quarterly declaration of the same
        filing year, so no other temporal member can produce it. The pin is a
        refusal because a binding that silently read a different period would
        publish a complete-looking annual total built from the wrong quarter.
        """
        if not isinstance(self.temporal, FiledCurrentPeriod) or self.temporal.source_period != StandardPeriodCode.Q4:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary temporal must be the filed last-quarter "
                "period of the target's own filing year",
            )
        return self


class M303RegimenSimplificadoAnnualSummaryRequirement(BaseModel):
    """Revision-owned target map for the one persisted 303 4T handoff."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    source_period: FilingPeriodCode
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId] = Field(min_length=1)
    dependency_treatment: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @field_validator("binding_ids_by_summary_casilla_id")
    @classmethod
    @pydantic_validation_boundary
    def _freeze_endpoint_bindings(cls, value: Mapping[CasillaId, BindingId]) -> Mapping[CasillaId, BindingId]:
        return dict(value)


def m303_regimen_simplificado_annual_summary_requirement(
    revision: ModeloRevision,
) -> M303RegimenSimplificadoAnnualSummaryRequirement | None:
    """Project the revision's typed Modelo 303 4T annual-summary bindings once.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    bindings = _annual_summary_bindings(revision)
    if not bindings:
        return None
    first_selector = provider_member(bindings[0], M303RegimenSimplificadoAnnualSummaryProvider)
    if len(first_selector.source_casilla_ids) != len(M390_SUMMARY_SOURCE_READ_ENDPOINTS):
        raise RegistryValidationError(
            "m303_regimen_simplificado_annual_summary selector must name one source casilla for each "
            f"source-read endpoint; found {len(first_selector.source_casilla_ids)}",
        )
    if not isinstance(first_selector.temporal, FiledCurrentPeriod):
        raise RegistryValidationError("m303_regimen_simplificado_annual_summary temporal must be a filed period")
    binding_ids_by_summary_casilla_id, legal_refs, source_refs = _collect_bindings(bindings, first_selector)
    return M303RegimenSimplificadoAnnualSummaryRequirement(
        source_modelo=first_selector.source_modelo,
        source_period=first_selector.temporal.source_period,
        source_casilla_ids=first_selector.source_casilla_ids,
        binding_ids_by_summary_casilla_id=binding_ids_by_summary_casilla_id,
        dependency_treatment=_dependency_treatment(revision, first_selector.source_modelo),
        legal_refs=tuple(sorted(legal_refs)),
        source_refs=tuple(sorted(source_refs)),
    )


def validate_m303_regimen_simplificado_annual_summary_revision(revision: ModeloRevision) -> list[str]:
    """Return build-time failures for the complete 303/4T -> 390/0A target map.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    try:
        requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    except RegistryValidationError as exc:
        return [str(exc)]
    if requirement is None:
        return []

    # The authoring revision is the authority at publish time. Runtime handoff
    # code deliberately never supplies a second endpoint catalogue.
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    return _endpoint_failures(requirement.binding_ids_by_summary_casilla_id, casillas_by_id)


def _annual_summary_bindings(revision: ModeloRevision) -> tuple[BindingDefinition, ...]:
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )


def _collect_bindings(
    bindings: tuple[BindingDefinition, ...],
    first_selector: M303RegimenSimplificadoAnnualSummaryProvider,
) -> tuple[dict[CasillaId, BindingId], set[LegalRefId], set[SourceRefId]]:
    binding_ids_by_summary_casilla_id: dict[CasillaId, BindingId] = {}
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = provider_member(binding, M303RegimenSimplificadoAnnualSummaryProvider)
        if (
            selector.source_modelo != first_selector.source_modelo
            or selector.temporal != first_selector.temporal
            or selector.source_casilla_ids != first_selector.source_casilla_ids
        ):
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary bindings must share one exact source selector",
            )
        existing = binding_ids_by_summary_casilla_id.get(selector.summary_casilla_id)
        if existing is not None:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary declares multiple bindings for "
                f"summary casilla {selector.summary_casilla_id!r}: {existing!r}, {binding.id!r}",
            )
        binding_ids_by_summary_casilla_id[selector.summary_casilla_id] = binding.id
        legal_refs.update(binding.legal_refs)
        source_refs.update(binding.source_refs)
    return binding_ids_by_summary_casilla_id, legal_refs, source_refs


def _dependency_treatment(revision: ModeloRevision, source_modelo: ModeloId) -> str:
    classification = next(
        (candidate for candidate in revision.dependency_classifications if candidate.source_modelo == source_modelo),
        None,
    )
    return "" if classification is None else str(classification.treatment)


def _endpoint_failures(
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Hold the declared endpoints to the form section that owns them.

    The endpoints must fill one section of the edition completely, each bound
    only by its own binding, and that section's boxes must carry consecutive
    numbers. The rule reads the edition's own casillas, so it holds for any
    edition without restating a box number, and nothing reads the declaration
    sequence, so permuting the binding fragments cannot reassign a box.
    """
    failures: list[str] = []
    sections: set[tuple[str, ...]] = set()
    for casilla_id, binding_id in binding_ids_by_summary_casilla_id.items():
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            failures.append(
                f"m303_regimen_simplificado_annual_summary endpoint {casilla_id!r} is not declared as a casilla",
            )
            continue
        sections.add(tuple(casilla.section))
        if casilla.input_kind is not InputKind.BOUND or bound_casilla_binding_ids(casilla) != (binding_id,):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must be bound only by {binding_id!r}",
            )
    if len(sections) > 1:
        failures.append(
            f"m303_regimen_simplificado_annual_summary endpoints span more than one form section: {sorted(sections)}",
        )
    for section in sorted(sections):
        failures.extend(_section_coverage_failures(section, binding_ids_by_summary_casilla_id, casillas_by_id))
    return failures


def _section_coverage_failures(
    section: tuple[str, ...],
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return the failures for a section the endpoints miss or whose numbering has a gap."""
    members = tuple(casilla for casilla in casillas_by_id.values() if tuple(casilla.section) == section)
    failures = [
        "m303_regimen_simplificado_annual_summary declares no endpoint for casilla number "
        f"{casilla.number!r} ({casilla.id!r}) of its form section"
        for casilla in members
        if casilla.id not in binding_ids_by_summary_casilla_id
    ]
    numbers = sorted(int(casilla.number) if casilla.number.isdecimal() else -1 for casilla in members)
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        numbered = {casilla.id: casilla.number for casilla in members}
        failures.append(
            f"m303_regimen_simplificado_annual_summary form section numbers its boxes out of sequence: {numbered}",
        )
    return failures
