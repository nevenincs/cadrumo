"""Immutable Modelo 303 4T to Modelo 390 0A simplified-regime handoff.

The annual Modelo 390 simplified-regime section is not a relation fold over
observations.  It consumes one exact, filed-and-current Modelo 303 calculation
revision and retains that source identity as a frozen target calculation input.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.decimal.constants import ZERO
from ...core.errors.hierarchy import CoreValidationError
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.m303_regimen_simplificado_annual_summary_bindings import (
    M390_SUMMARY_ACTIVOS_FIJOS_DEVENGADA,
    M390_SUMMARY_AGRICULTURAL_RESULT,
    M390_SUMMARY_AIC_DEVENGADA,
    M390_SUMMARY_DEVENGADA_TOTAL,
    M390_SUMMARY_ISP_DEVENGADA,
    M390_SUMMARY_NON_AGRICULTURAL_RESULT,
    M390_SUMMARY_REGULARIZACION,
    M390_SUMMARY_RESULTADO,
    M390_SUMMARY_SOPORTADO_ACTIVOS_FIJOS,
    M390_SUMMARY_SOURCE_READ_ENDPOINTS,
    M390_SUMMARY_SUMA_DEDUCCIONES,
    M303RegimenSimplificadoAnnualSummaryRequirement,
    m303_regimen_simplificado_annual_summary_requirement,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.iva.regimen_simplificado_rows import ActividadAgricolaSimplificado
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
)
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
)
from ...domain.modelos.calculation_revision_m303_handoff import (
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from ...domain.modelos.filing_record import ModeloRecordStatus
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceProvenance, CalculationSourceResolution
from .revision_carry_gate import revision_carry_outcome

_SOURCE_KIND = BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY


class M303RegimenSimplificadoAnnualSummaryHandoffError(CoreValidationError):
    """Raised when a Modelo 390 annual handoff has no exact filed 303 source.

    Roots at :class:`~core.errors.hierarchy.CoreValidationError` like every other refusal
    in this package, so the class binds to the error registry and its refusal
    carries a code, a category and locale-resolved text. That base already
    carries :exc:`ValueError`, so the resolver keeps the ancestry its callers
    were written against.
    """


class M303RegimenSimplificadoAnnualSummarySourceResolver:
    """Resolve the one immutable filed-current 303/4T annual-summary source."""

    resolver_id: ClassVar[str] = _SOURCE_KIND.value
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        registry_snapshot: RegistrySnapshot,
        work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
        calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
        filing_repository: ModeloRecordCatalogueRepositoryProtocol,
        regimen_simplificado_applies: bool,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Initialize the resolver with the repositories and applicability flag it draws on."""
        self._registry_snapshot = registry_snapshot
        self._work_unit_repository = work_unit_repository
        self._calculation_repository = calculation_repository
        self._filing_repository = filing_repository
        self._operation = operation
        #: Whether regimen simplificado reaches this taxpayer at all. Supplied
        #: rather than derived: the closed scope vocabulary is single-homed in
        #: the modelo package, and this layer already receives its scope
        #: decision instead of reaching across the package boundary for one.
        self._regimen_simplificado_applies = regimen_simplificado_applies

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Assemble the exact annual-summary inputs or refuse before target persistence."""
        requirement = m303_regimen_simplificado_annual_summary_requirement(context.revision)
        if requirement is None or not self._regimen_simplificado_applies:
            # The summary boxes exist on every annual form, so the revision
            # declaring this family says what the FORM carries, never that the
            # regime reaches this taxpayer. LIVA art. 122 Uno applies regimen
            # simplificado only to sujetos pasivos meeting its three stated
            # requirements; a regimen general filer meets none, and the source
            # boxes this family reads carry nothing for them. Demanding
            # the source anyway would refuse an ordinary annual resumen. The
            # boxes stay without a value, and the resolution says they do not
            # apply, so no diagnostic reports them as a missing source.
            inapplicable = tuple(binding.id for binding in context.revision.bindings if binding.source is _SOURCE_KIND)
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                inapplicable_binding_ids=inapplicable,
            )
        target = self._target_work_unit(context)
        self._require_target_matches_snapshot(target, context)
        source = self._source_work_unit(target, requirement)
        source_revision = self._filed_current_source_revision(source)
        result, evidence_references = self._validated_source_evidence(source, source_revision)
        source_values = self._source_values(source_revision.casilla_values, requirement.source_casilla_ids)
        values = self._summary_values(result.activities, source_values, requirement.source_casilla_ids)
        self._require_arithmetic_coherence(values)
        self._require_registry_target_map(requirement.binding_ids_by_summary_casilla_id, values)
        handoff = M303RegimenSimplificadoAnnualSummaryHandoff.assembled(
            source_bucket_id=source.bucket_id,
            source_modelo=source.modelo,
            source_work_unit_id=source.work_unit_id,
            source_calculation_revision_id=source_revision.calculation_revision_id,
            source_registry_revision_id=source.revision_id,
            source_filing_year=source.filing_year,
            source_period_code=source.period.registry_token,
            source_result_digest=result.digest,
            source_evidence_references=evidence_references,
            target_bucket_id=target.bucket_id,
            target_modelo=target.modelo,
            target_work_unit_id=target.work_unit_id,
            target_registry_revision_id=target.revision_id,
            target_filing_year=target.filing_year,
            target_period_code=target.period.registry_token,
            values=values,
        )
        self._require_registry_coordinates_current(handoff)
        binding_values = {
            binding_id: values[casilla_id]
            for casilla_id, binding_id in requirement.binding_ids_by_summary_casilla_id.items()
        }
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            m303_regimen_simplificado_annual_summary_handoff=handoff,
            provenance=(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=_SOURCE_KIND,
                    contributor_source_kind=_SOURCE_KIND.value,
                    contributor_binding_source=_SOURCE_KIND,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=(
                        "m303-regimen-simplificado-annual-summary:"
                        f"{source.work_unit_id}:{source_revision.calculation_revision_id}"
                    ),
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.FILED_MODELO_CASILLA,
                    fingerprint=handoff.digest,
                    source_modelo=requirement.source_modelo,
                    source_filing_year=source.filing_year,
                    source_periods=(requirement.source_period,),
                    source_casilla_ids=requirement.source_casilla_ids,
                    legal_refs=requirement.legal_refs,
                    source_refs=requirement.source_refs,
                    dependency_treatment=requirement.dependency_treatment,
                ),
            ),
        )

    def validate_persisted_target_revision(
        self,
        *,
        target_work_unit: WorkUnit,
        target_revision: CalculationRevision,
    ) -> None:
        """Re-resolve and compare the immutable handoff before target use.

        Calculation stores the carrier only after the target revision id has
        been derived.  Verification, filing, and export re-run this exact
        source selection so a later source-pointer/evidence/result drift cannot
        be hidden behind an otherwise valid target-revision hash.

        Core types:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
        """
        requirement = m303_regimen_simplificado_annual_summary_requirement(self._registry_snapshot.revision)
        persisted = target_revision.m303_regimen_simplificado_annual_summary_handoff
        # An inapplicable family is indistinguishable from an undeclared one
        # here: neither can produce a handoff, so a persisted one is equally
        # anomalous and an absent one equally correct.
        if requirement is None or not self._regimen_simplificado_applies:
            if persisted is not None:
                raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                    "M303 annual-summary handoff is present on a target revision without its registry requirement",
                )
            return
        if persisted is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary target revision is missing its immutable handoff",
            )
        self._require_registry_coordinates_current(persisted)
        if target_revision.work_unit_id != target_work_unit.work_unit_id:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary target revision does not belong to its target work unit",
            )
        resolved = self.resolve(
            CalculationSourceContext(
                bucket_id=target_work_unit.bucket_id,
                work_unit_id=target_work_unit.work_unit_id,
                modelo=target_work_unit.modelo,
                filing_year=target_work_unit.filing_year,
                period=target_work_unit.period,
                revision=self._registry_snapshot.revision,
            ),
        ).m303_regimen_simplificado_annual_summary_handoff
        if resolved is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary resolver did not produce the required immutable handoff",
            )
        expected = resolved.stamped_for_target_calculation_revision(target_revision.calculation_revision_id)
        if persisted != expected:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary persisted handoff no longer matches its exact filed source",
            )

    def _require_registry_coordinates_current(self, handoff: M303RegimenSimplificadoAnnualSummaryHandoff) -> None:
        for snapshot_ref in (handoff.source_registry_snapshot_ref, handoff.target_registry_snapshot_ref):
            outcome = revision_carry_outcome(snapshot_ref, operation=self._operation)
            if outcome.refused:
                raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                    "M303 annual-summary registry coordinate cannot be re-confirmed: "
                    f"{snapshot_ref.revision_id}: {outcome.detail}"
                )

    def _target_work_unit(self, context: CalculationSourceContext) -> WorkUnit:
        if context.work_unit_id is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff requires the exact target work-unit identity",
            )
        target = self._work_unit_repository.load().get(context.work_unit_id)
        if target is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                f"M303 annual-summary handoff target work unit {context.work_unit_id!r} is unavailable",
            )
        return target

    def _require_target_matches_snapshot(self, target: WorkUnit, context: CalculationSourceContext) -> None:
        if (
            target.bucket_id != context.bucket_id
            or target.modelo != context.modelo
            or target.filing_year != context.filing_year
            or target.period != context.period
            or target.revision_id != context.revision.id
            or self._registry_snapshot.revision.id != context.revision.id
        ):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff target must be the selected annual work unit and revision",
            )

    def _source_work_unit(
        self,
        target: WorkUnit,
        requirement: M303RegimenSimplificadoAnnualSummaryRequirement,
    ) -> WorkUnit:
        expected_period = Period.from_year_and_code(target.filing_year, requirement.source_period)
        candidates = tuple(
            item
            for item in self._work_unit_repository.load()
            if (
                item.bucket_id == target.bucket_id
                and item.modelo == requirement.source_modelo
                and item.filing_year == target.filing_year
                and item.period == expected_period
            )
        )
        if len(candidates) != 1:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff requires exactly one same-bucket filed source work unit; "
                f"found {len(candidates)}",
            )
        return candidates[0]

    def _filed_current_source_revision(self, source: WorkUnit) -> CalculationRevision:
        revision = self._filed_source_revision(source)
        self._require_current_filing_record(source, revision)
        return revision

    def _filed_source_revision(self, source: WorkUnit) -> CalculationRevision:
        filed_id = source.filed_calculation_revision_id
        if filed_id is None or source.current_calculation_revision_id != filed_id:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff requires the current calculation pointer to equal the filed revision",
            )
        revision = self._calculation_repository.load(operation=self._operation).get(filed_id)
        if revision is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                f"M303 annual-summary handoff filed calculation revision {filed_id!r} is unavailable",
            )
        outcome = revision_carry_outcome(revision.registry_snapshot_ref, operation=self._operation)
        if outcome.refused:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary source calculation coordinate cannot be re-confirmed: "
                f"{revision.registry_snapshot_ref.revision_id}: {outcome.detail}",
            )
        if revision.work_unit_id != source.work_unit_id or revision.state is not CalculationRevisionState.PRESENTADO:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff source must resolve to its own PRESENTADO calculation revision",
            )
        return revision

    def _require_current_filing_record(self, source: WorkUnit, revision: CalculationRevision) -> None:
        filing_id = source.current_filing_record_id
        if filing_id is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff source work unit has no current filing record",
            )
        filing_catalogue = self._filing_repository.load()
        filing = filing_catalogue.get(filing_id)
        current = filing_catalogue.current_for(
            bucket_id=source.bucket_id,
            modelo=source.modelo,
            filing_year=source.filing_year,
            period=source.period,
        )
        if (
            filing is None
            or filing is not current
            or filing.status is not ModeloRecordStatus.VIGENTE
            or filing.work_unit_id != source.work_unit_id
            or filing.calculation_revision_id != revision.calculation_revision_id
        ):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff requires the VIGENTE filing record for the exact filed revision",
            )

    def _validated_source_evidence(
        self,
        source: WorkUnit,
        source_revision: CalculationRevision,
    ) -> tuple[M303RegimenSimplificadoCalculationResult, tuple[FilingEvidenceReference, ...]]:
        evidence = source_revision.filing_instance_evidence
        if evidence is None:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff requires persisted filing-instance evidence",
            )
        m303 = evidence.m303
        result = m303.regimen_simplificado.calculation_result
        source_revision_at_coordinate = self._operation.revision_for_context(
            source.modelo,
            filing_year=source.filing_year,
            period=source.period.registry_token,
        )
        self._require_source_evidence_coordinate(
            source,
            source_revision,
            m303,
            result,
            source_revision_at_coordinate.id,
        )
        self._require_non_agricultural_rows(m303)
        evidence_references = tuple(
            reference for activity in result.activities for reference in activity.evidence_references
        )
        return result, evidence_references

    def _require_source_evidence_coordinate(
        self,
        source: WorkUnit,
        source_revision: CalculationRevision,
        m303: M303FilingInstanceEvidence,
        result: M303RegimenSimplificadoCalculationResult,
        source_revision_id: RevisionId,
    ) -> None:
        if (
            m303.period,
            result.period,
            result.ejercicio,
            result.registry_revision_id,
            source_revision_id,
            source_revision.work_unit_id,
        ) != (
            source.period,
            source.period,
            source.filing_year,
            source.revision_id,
            source.revision_id,
            source.work_unit_id,
        ):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff source evidence/result/revision coordinate diverges from its work unit",
            )

    def _require_non_agricultural_rows(self, m303: M303FilingInstanceEvidence) -> None:
        if any(isinstance(row, ActividadAgricolaSimplificado) for row in m303.regimen_simplificado.rows.activities):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary handoff refuses agricultural simplified-regime rows until "
                "their annual Orden authority resolves",
            )

    def _source_values(
        self,
        casilla_values: Mapping[CasillaId, Decimal],
        declared_source_ids: tuple[CasillaId, ...],
    ) -> Mapping[CasillaId, Decimal]:
        missing = tuple(casilla_id for casilla_id in declared_source_ids if casilla_id not in casilla_values)
        if missing:
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                f"M303 annual-summary source calculation is missing casillas {missing!r}",
            )
        return {casilla_id: casilla_values[casilla_id] for casilla_id in declared_source_ids}

    def _summary_values(
        self,
        activities: tuple[M303RegimenSimplificadoActivityCalculationResult, ...],
        source_values: Mapping[CasillaId, Decimal],
        declared_source_ids: tuple[CasillaId, ...],
    ) -> Mapping[CasillaId, Decimal]:
        non_agricultural_result = sum((item.cuota_resultante for item in activities), start=ZERO)
        return {
            M390_SUMMARY_NON_AGRICULTURAL_RESULT: non_agricultural_result,
            M390_SUMMARY_AGRICULTURAL_RESULT: ZERO,
            **{
                endpoint: source_values[source_id]
                for endpoint, source_id in zip(M390_SUMMARY_SOURCE_READ_ENDPOINTS, declared_source_ids, strict=True)
            },
        }

    def _require_arithmetic_coherence(self, values: Mapping[CasillaId, Decimal]) -> None:
        devengada_parts = (
            M390_SUMMARY_NON_AGRICULTURAL_RESULT,
            M390_SUMMARY_AGRICULTURAL_RESULT,
            M390_SUMMARY_AIC_DEVENGADA,
            M390_SUMMARY_ISP_DEVENGADA,
            M390_SUMMARY_ACTIVOS_FIJOS_DEVENGADA,
        )
        if values[M390_SUMMARY_DEVENGADA_TOTAL] != sum((values[part] for part in devengada_parts), start=ZERO):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary source devengada total disagrees with its declared parts",
            )
        if values[M390_SUMMARY_SUMA_DEDUCCIONES] != (
            values[M390_SUMMARY_SOPORTADO_ACTIVOS_FIJOS] + values[M390_SUMMARY_REGULARIZACION]
        ):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary source deduction total disagrees with its declared parts",
            )
        if values[M390_SUMMARY_RESULTADO] != (
            values[M390_SUMMARY_DEVENGADA_TOTAL] - values[M390_SUMMARY_SUMA_DEDUCCIONES]
        ):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary source result disagrees with its declared devengada and deductions",
            )

    def _require_registry_target_map(
        self,
        binding_ids_by_summary_casilla_id: Mapping[CasillaId, str],
        values: Mapping[CasillaId, Decimal],
    ) -> None:
        if set(values) != set(binding_ids_by_summary_casilla_id):
            raise M303RegimenSimplificadoAnnualSummaryHandoffError(
                "M303 annual-summary assembler did not produce the exact declared endpoint set",
            )


def validate_m303_regimen_simplificado_annual_summary_target_revision(
    *,
    target_work_unit: WorkUnit,
    target_revision: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    regimen_simplificado_applies: bool,
    operation: PinnedAuthorityOperation,
) -> None:
    """Fail closed when a persisted M390 handoff no longer re-resolves exactly.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    # The calculation rung, not the filing rung. This precondition asks the
    # revision whether it DECLARES the annual-summary requirement and, when it
    # does, re-resolves the sources behind the persisted handoff. It renders no
    # fichero and reads no export layout, so demanding filing authority refuses
    # a calculation-grade modelo before the registry can answer "this
    # requirement does not apply to you" -- and the check still runs, still
    # reads the requirement, and still raises on a handoff present without one.
    snapshot = operation.snapshot(
        target_work_unit.modelo,
        filing_year=target_work_unit.filing_year,
        period=target_work_unit.period.registry_token,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    M303RegimenSimplificadoAnnualSummarySourceResolver(
        registry_snapshot=snapshot,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        regimen_simplificado_applies=regimen_simplificado_applies,
        operation=operation,
    ).validate_persisted_target_revision(
        target_work_unit=target_work_unit,
        target_revision=target_revision,
    )


__all__ = [
    "M303RegimenSimplificadoAnnualSummaryHandoffError",
    "M303RegimenSimplificadoAnnualSummarySourceResolver",
    "validate_m303_regimen_simplificado_annual_summary_target_revision",
]
