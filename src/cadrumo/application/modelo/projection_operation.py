"""Registered Modelo 100 projection and cross-year comparison operations."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FourDigitYear, is_four_digit_year
from ...core.i18n.render import output_language
from ...core.identity.digest import ContentDigest
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ..ledger.persistence_ports import LedgerPersistenceConflictError
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from .projection import (
    ModeloProjectServiceResult,
    project_modelo_100_from_m130,
)
from .projection_compare import ModeloCompareServiceResult, compare_modelo_years
from .projection_migration_ports import ProjectionMigrationPlan, ProjectionMigrationPort
from .projection_unresolved import (
    ModeloProjectionUnresolvedBinding,
    ModeloProjectionUnresolvedCasilla,
)
from .projection_words import (
    binding_source_words,
    m100_figure_words,
    m130_figure_words,
    unresolved_binding_words,
    unresolved_casilla_reason_words,
)

MODELO_PROJECT_OPERATION_DEFINITION_ID = "modelo.project"
MODELO_COMPARE_OPERATION_DEFINITION_ID = "modelo.compare"

_Token = Annotated[str, Field(min_length=1, max_length=128)]
_Value = Annotated[str, Field(min_length=1, max_length=16_384)]
_Words = Annotated[str, Field(min_length=1, max_length=1_024)]
_LOG = get_logger(__name__)


class ProjectionOverride(BaseModel):
    """One operator supplied, unsaved input for a projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: _Token
    value: _Value


class ModeloProjectOperationRequest(CredentialFreeOperationRequest):
    """Address one annual projection and its exact temporary overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: FourDigitYear
    #: The region to project for. Left out, it is the region the exact profile's
    #: tax residence states; a profile that states none is refused.
    ccaa: _Token | None = None
    casilla_overrides: tuple[ProjectionOverride, ...] = ()
    binding_overrides: tuple[ProjectionOverride, ...] = ()

    @model_validator(mode="after")
    def _unique_overrides(self) -> Self:
        for overrides in (self.casilla_overrides, self.binding_overrides):
            if len({item.key for item in overrides}) != len(overrides):
                raise ValueError("projection override identifiers must be unique")
        return self


class ModeloCompareOperationRequest(CredentialFreeOperationRequest):
    """Address the two complete filing-year histories to compare."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    modelo: _Token
    years: tuple[int, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _two_years(self) -> Self:
        if len(self.years) != 2 or not all(is_four_digit_year(year) for year in self.years):
            raise ValueError("comparison needs two filing years")
        return self


class ProjectM130AccumulatedWords(BaseModel):
    """The name of each cumulative quarterly-declaration figure, in the projection's ``words_language``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ingresos: _Words
    gastos: _Words
    rendimiento_neto: _Words
    pagos_fraccionados: _Words


class ProjectM130AccumulatedProjection(BaseModel):
    """All four canonical cumulative M130 summary values, each with its name in words."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ingresos: _Value
    gastos: _Value
    rendimiento_neto: _Value
    pagos_fraccionados: _Value
    words: ProjectM130AccumulatedWords


class ProjectM100SummaryWords(BaseModel):
    """The name of each projected annual-return figure, in the projection's ``words_language``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    base_liquidable_general: _Words
    pagos_fraccionados: _Words
    cuota_integra_estatal: _Words
    cuota_integra_autonomica: _Words
    cuota_liquida_estatal: _Words
    cuota_liquida_autonomica: _Words
    cuota_resultante: _Words


class ProjectM100SummaryProjection(BaseModel):
    """All seven canonical M100 summary values, each with its name in words."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    base_liquidable_general: _Value
    pagos_fraccionados: _Value
    cuota_integra_estatal: _Value
    cuota_integra_autonomica: _Value
    cuota_liquida_estatal: _Value
    cuota_liquida_autonomica: _Value
    cuota_resultante: _Value
    words: ProjectM100SummaryWords


class ProjectCasillaObservationProjection(BaseModel):
    """One calculated value and its unabridged grounding references."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: _Token
    value: _Value
    formula_id: _Token | None
    legal_refs: tuple[_Token, ...]
    source_refs: tuple[_Token, ...]


class ProjectUnresolvedBindingProjection(BaseModel):
    """One source-owned binding left without a value, named by its box and closed tokens.

    ``words`` says why it has no value and what puts that right, and
    ``source_words`` names its source in a few words (``None`` for a source kind
    the product does not know); both are in the projection's ``words_language``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    binding_id: _Token
    casilla_id: _Token | None
    #: The number the form prints for that box; ``None`` for a working figure or when no box is named.
    box: _Token | None = None
    source_kind: _Token
    reason: _Token
    note: _Token | None
    source_words: _Words | None
    words: _Words

    @classmethod
    def from_service(cls, row: ModeloProjectionUnresolvedBinding, *, language: OutputLanguage) -> Self:
        """Name one unresolved binding and the words that explain it in ``language``."""
        return cls(
            binding_id=row.binding_id,
            casilla_id=row.casilla_id,
            box=row.box,
            source_kind=row.source_kind,
            reason=row.reason,
            note=str(row.note) if row.note is not None else None,
            source_words=binding_source_words(row.source_kind, language=language),
            words=unresolved_binding_words(row.fact, language=language),
        )


class ProjectUnresolvedCasillaProjection(BaseModel):
    """One computed box with no value, and the grounding of the formula that would compute it.

    ``reason_words`` says why it has no value, in the projection's ``words_language``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: _Token
    #: The number the form prints for the box; ``None`` for a working figure the form does not print.
    box: _Token | None = None
    reason: _Token
    reason_words: _Words
    formula_id: _Token
    legal_refs: tuple[_Token, ...]
    source_refs: tuple[_Token, ...]

    @classmethod
    def from_service(cls, row: ModeloProjectionUnresolvedCasilla, *, language: OutputLanguage) -> Self:
        """Carry one unresolved box with the words for its reason in ``language``."""
        return cls(
            casilla_id=row.casilla_id,
            box=row.box,
            reason=row.reason,
            reason_words=unresolved_casilla_reason_words(row.reason, language=language),
            formula_id=row.formula_id,
            legal_refs=tuple(row.legal_refs),
            source_refs=tuple(row.source_refs),
        )


def require_unresolved_boxes_carry_no_value(
    observed: Collection[str],
    bindings: Iterable[ProjectUnresolvedBindingProjection],
    casillas: Iterable[ProjectUnresolvedCasillaProjection],
) -> None:
    """Refuse a result in which a box with no value also carries one."""
    unresolved = {row.casilla_id for row in casillas} | {
        row.casilla_id for row in bindings if row.casilla_id is not None
    }
    if unresolved.intersection(observed):
        raise ValueError("an unresolved projected box also carries a value")


class ModeloProjectOperationProjection(BaseModel):
    """The complete public projection, bound to its source profile.

    A box in ``unresolved_casillas`` or bound by a binding in
    ``unresolved_bindings`` has no value, and never appears in
    ``casilla_observations``. The words of both lists, and the name of each
    figure in ``m130_accumulated`` and ``m100_projection``, are in
    ``words_language``, the language the worker's catalogue rendered them in.
    ``ccaa`` is the region the projection was made for, whether the request
    named it or the profile's tax residence did.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[3] = 3
    authority_generation: ContentDigest
    profile_id: UUID
    year: FourDigitYear
    ccaa: _Token
    quarters_filed: int = Field(ge=1, le=4)
    quarters_available: tuple[_Token, ...]
    is_extrapolated: bool
    m130_accumulated: ProjectM130AccumulatedProjection
    casilla_observations: tuple[ProjectCasillaObservationProjection, ...]
    m100_projection: ProjectM100SummaryProjection
    unresolved_bindings: tuple[ProjectUnresolvedBindingProjection, ...]
    unresolved_casillas: tuple[ProjectUnresolvedCasillaProjection, ...]
    words_language: OutputLanguage

    @model_validator(mode="after")
    def _complete_quarters(self) -> Self:
        if self.quarters_filed != len(self.quarters_available) or len(set(self.quarters_available)) != len(
            self.quarters_available
        ):
            raise ValueError("projected quarter count or identities disagree")
        return self

    @model_validator(mode="after")
    def _unresolved_boxes_carry_no_value(self) -> Self:
        require_unresolved_boxes_carry_no_value(
            {row.casilla_id for row in self.casilla_observations},
            self.unresolved_bindings,
            self.unresolved_casillas,
        )
        return self

    @classmethod
    def from_service(
        cls, profile_id: UUID, result: ModeloProjectServiceResult, *, authority_generation: ContentDigest
    ) -> Self:
        """Carry all canonical values and per-casilla provenance without rounding."""
        language = OutputLanguage(output_language())
        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            year=result.year,
            ccaa=result.ccaa,
            quarters_filed=result.quarters_filed,
            quarters_available=result.quarters_available,
            is_extrapolated=result.is_extrapolated,
            m130_accumulated=ProjectM130AccumulatedProjection(
                ingresos=_decimal(result.m130_accumulated.ingresos),
                gastos=_decimal(result.m130_accumulated.gastos),
                rendimiento_neto=_decimal(result.m130_accumulated.rendimiento_neto),
                pagos_fraccionados=_decimal(result.m130_accumulated.pagos_fraccionados),
                words=ProjectM130AccumulatedWords(
                    ingresos=m130_figure_words("ingresos", language=language),
                    gastos=m130_figure_words("gastos", language=language),
                    rendimiento_neto=m130_figure_words("rendimiento_neto", language=language),
                    pagos_fraccionados=m130_figure_words("pagos_fraccionados", language=language),
                ),
            ),
            casilla_observations=tuple(
                ProjectCasillaObservationProjection(
                    casilla_id=row.casilla_id,
                    value=_decimal(row.value),
                    formula_id=row.formula_id,
                    legal_refs=tuple(row.legal_refs),
                    source_refs=tuple(row.source_refs),
                )
                for row in result.casilla_observations
            ),
            m100_projection=ProjectM100SummaryProjection(
                base_liquidable_general=_decimal(result.m100_projection.base_liquidable_general),
                pagos_fraccionados=_decimal(result.m100_projection.pagos_fraccionados),
                cuota_integra_estatal=_decimal(result.m100_projection.cuota_integra_estatal),
                cuota_integra_autonomica=_decimal(result.m100_projection.cuota_integra_autonomica),
                cuota_liquida_estatal=_decimal(result.m100_projection.cuota_liquida_estatal),
                cuota_liquida_autonomica=_decimal(result.m100_projection.cuota_liquida_autonomica),
                cuota_resultante=_decimal(result.m100_projection.cuota_resultante),
                words=ProjectM100SummaryWords(
                    base_liquidable_general=m100_figure_words("base_liquidable_general", language=language),
                    pagos_fraccionados=m100_figure_words("pagos_fraccionados", language=language),
                    cuota_integra_estatal=m100_figure_words("cuota_integra_estatal", language=language),
                    cuota_integra_autonomica=m100_figure_words("cuota_integra_autonomica", language=language),
                    cuota_liquida_estatal=m100_figure_words("cuota_liquida_estatal", language=language),
                    cuota_liquida_autonomica=m100_figure_words("cuota_liquida_autonomica", language=language),
                    cuota_resultante=m100_figure_words("cuota_resultante", language=language),
                ),
            ),
            unresolved_bindings=tuple(
                ProjectUnresolvedBindingProjection.from_service(row, language=language)
                for row in result.unresolved_bindings
            ),
            unresolved_casillas=tuple(
                ProjectUnresolvedCasillaProjection.from_service(row, language=language)
                for row in result.unresolved_casillas
            ),
            words_language=language,
        )


class CompareDeltaRowProjection(BaseModel):
    """One full comparison row and its recorded provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: _Token
    label: _Value
    section: _Token
    year_a_value: _Value
    year_b_value: _Value
    delta: _Value
    pct_change: _Value | None
    formula_id: _Token | None
    legal_refs: tuple[_Token, ...]
    source_refs: tuple[_Token, ...]


class CompareSectionProjection(BaseModel):
    """One canonical first-seen section and every row inside it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    section: _Token
    rows: tuple[CompareDeltaRowProjection, ...]


class ModeloCompareOperationProjection(BaseModel):
    """Complete year-pair comparison, including flattened and sectioned rows."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    authority_generation: ContentDigest
    profile_id: UUID
    modelo: _Token
    year_a: FourDigitYear
    year_b: FourDigitYear
    year_a_revision_id: _Token
    year_b_revision_id: _Token
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: tuple[CompareSectionProjection, ...]
    delta_rows: tuple[CompareDeltaRowProjection, ...]

    @model_validator(mode="after")
    def _complete_ordered_rows(self) -> Self:
        if self.year_a > self.year_b:
            raise ValueError("comparison years are not canonically ordered")
        first_seen = tuple(dict.fromkeys(row.section for row in self.delta_rows))
        if tuple(section.section for section in self.sections) != first_seen:
            raise ValueError("comparison sections differ from first-seen row order")
        if any(
            section.rows != tuple(row for row in self.delta_rows if row.section == section.section)
            for section in self.sections
        ):
            raise ValueError("comparison section rows differ from flat rows")
        return self

    @classmethod
    def from_service(
        cls, profile_id: UUID, result: ModeloCompareServiceResult, *, authority_generation: ContentDigest
    ) -> Self:
        """Carry duplicate section/flat views with their complete provenance."""
        rows = tuple(_compare_row(row) for row in result.delta_rows)
        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            modelo=result.modelo,
            year_a=result.year_a,
            year_b=result.year_b,
            year_a_revision_id=result.year_a_revision_id,
            year_b_revision_id=result.year_b_revision_id,
            year_a_is_draft=result.year_a_is_draft,
            year_b_is_draft=result.year_b_is_draft,
            sections=tuple(
                CompareSectionProjection(section=section.section, rows=tuple(_compare_row(row) for row in section.rows))
                for section in result.sections
            ),
            delta_rows=rows,
        )


def _decimal(value: object) -> str:
    from decimal import Decimal

    if not isinstance(value, Decimal):
        raise TypeError("canonical modelo projection value is not Decimal")
    return str(value)


def _compare_row(row: object) -> CompareDeltaRowProjection:
    from .projection_compare import ModeloCompareDeltaRow

    if not isinstance(row, ModeloCompareDeltaRow):
        raise TypeError("canonical comparison row has changed type")
    return CompareDeltaRowProjection(
        casilla_id=row.casilla_id,
        label=row.label,
        section=row.section,
        year_a_value=_decimal(row.year_a_value),
        year_b_value=_decimal(row.year_b_value),
        delta=_decimal(row.delta),
        pct_change=_decimal(row.pct_change) if row.pct_change is not None else None,
        formula_id=row.formula_id,
        legal_refs=tuple(row.legal_refs),
        source_refs=tuple(row.source_refs),
    )


@dataclass(frozen=True, slots=True)
class _ReadOnlyMigrationGuard:
    """Keep canonical revision reads, replacing their hidden write with a check."""

    port: ProjectionMigrationPort

    def migrate(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> None:
        self.port.assert_current(repository, operation=operation)


def _bound_ports(
    factory: CalculationActionPortsFactory, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> CalculationActionPorts:
    profile = str(profile_id)
    ports = factory(bucket_id=profile, operation=operation)
    if (
        ports.operation is not operation
        or ports.calculation_repository.bucket_id != profile
        or ports.work_unit_repository.bucket_id != profile
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


async def prepare_and_maybe_commit(
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    migration: ProjectionMigrationPort,
    context: OperationExecutorContext,
    phase_prefix: str,
) -> ProjectionMigrationPlan:
    """Run the pure full-catalogue plan, fencing only its possible CAS write."""
    await context.events.effect(OperationEffect.NONE)
    await context.events.phase(phase_prefix + ".prepare")
    plan = await asyncio.to_thread(migration.prepare, calculation_repository, operation=context.authority_operation)
    if not plan.changed:
        return plan
    async with context.cancellation.irreversible_section():
        await context.events.phase(phase_prefix + ".commit")
        await context.events.effect(OperationEffect.UNKNOWN)
        try:
            await asyncio.to_thread(migration.commit, calculation_repository, plan)
        except LedgerPersistenceConflictError:
            # A guarded CAS conflict occurs before this singleton write.
            await context.events.effect(OperationEffect.NONE)
            raise
        await context.events.effect(OperationEffect.UPDATED)
    _LOG.info(
        "rekeyed persisted calculation-revision relation overrides onto binding ids",
        extra={
            "reason": "calculation-revision:relation-override-binding-rekey",
            "rekeyed_revision_count": len(plan.revision_id_pairs),
            "rekeyed_override_key_count": len(plan.override_key_pairs),
            "revision_id_pairs": plan.revision_id_pairs,
            "override_key_pairs": plan.override_key_pairs,
        },
    )
    return plan


class ModeloProjectExecutor:
    """Use the pinned catalogue and canonical projector after migration settlement."""

    def __init__(self, factory: CalculationActionPortsFactory, migration: ProjectionMigrationPort) -> None:
        self._factory = factory
        self._migration = migration

    async def execute(
        self, request: OperationRequest[ModeloProjectOperationRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if not valid_execution(
            request, context, profile_id=payload.profile_id, definition_id=MODELO_PROJECT_OPERATION_DEFINITION_ID
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        ports = _bound_ports(self._factory, profile_id=payload.profile_id, operation=context.authority_operation)

        async def run() -> str:
            await prepare_and_maybe_commit(
                calculation_repository=ports.calculation_repository,
                migration=self._migration,
                context=context,
                phase_prefix="modelo.project",
            )
            guarded = replace(ports, relation_override_migration=_ReadOnlyMigrationGuard(self._migration))
            result = await asyncio.to_thread(
                project_modelo_100_from_m130,
                year=payload.year,
                ccaa=payload.ccaa,
                bucket_id=str(payload.profile_id),
                ports=guarded,
                operation=context.authority_operation,
                casilla_overrides={item.key: item.value for item in payload.casilla_overrides},
                binding_overrides={item.key: item.value for item in payload.binding_overrides},
            )
            public = ModeloProjectOperationProjection.from_service(
                payload.profile_id,
                result,
                authority_generation=context.authority_operation.generation.logical_generation,
            )
            await context.events.phase("modelo.project.result")
            return await context.operands.put(public, written_at=now())

        return await await_cancellation_complete(run(), task_name="modelo-project")


class ModeloCompareExecutor:
    """Compare persisted year pairs through the canonical service and read guard."""

    def __init__(self, factory: CalculationActionPortsFactory, migration: ProjectionMigrationPort) -> None:
        self._factory = factory
        self._migration = migration

    async def execute(
        self, request: OperationRequest[ModeloCompareOperationRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if not valid_execution(
            request, context, profile_id=payload.profile_id, definition_id=MODELO_COMPARE_OPERATION_DEFINITION_ID
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        ports = _bound_ports(self._factory, profile_id=payload.profile_id, operation=context.authority_operation)

        async def run() -> str:
            await prepare_and_maybe_commit(
                calculation_repository=ports.calculation_repository,
                migration=self._migration,
                context=context,
                phase_prefix="modelo.compare",
            )
            guarded = replace(ports, relation_override_migration=_ReadOnlyMigrationGuard(self._migration))
            result = await asyncio.to_thread(
                compare_modelo_years,
                modelo=payload.modelo,
                years=payload.years,
                ports=guarded,
                operation=context.authority_operation,
            )
            public = ModeloCompareOperationProjection.from_service(
                payload.profile_id,
                result,
                authority_generation=context.authority_operation.generation.logical_generation,
            )
            await context.events.phase("modelo.compare.result")
            return await context.operands.put(public, written_at=now())

        return await await_cancellation_complete(run(), task_name="modelo-compare")


def valid_execution[Payload: BaseModel](
    request: OperationRequest[Payload],
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    definition_id: str,
) -> bool:
    """Return whether a request and context both address the given definition and profile."""
    subject = profile_operation_subject(str(profile_id))
    return (
        request.definition_id == definition_id
        and request.subject_ref == subject
        and context.identity.definition_id == definition_id
        and context.identity.subject_ref == subject
        and require_active_bucket_id() == str(profile_id)
    )


def _definition(
    *,
    definition_id: str,
    request_type: type[ModeloProjectOperationRequest] | type[ModeloCompareOperationRequest],
    result_type: type[ModeloProjectOperationProjection] | type[ModeloCompareOperationProjection],
    executor_type: type[ModeloProjectExecutor] | type[ModeloCompareExecutor],
    factory: CalculationActionPortsFactory,
    migration: ProjectionMigrationPort,
    public_error_detail: bool = False,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=lambda: executor_type(factory, migration),
        ),
        phase_codes=(definition_id + ".prepare", definition_id + ".commit", definition_id + ".result"),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        public_error_detail=public_error_detail,
    )


def build_modelo_project_definition(
    *, factory: CalculationActionPortsFactory, migration: ProjectionMigrationPort
) -> OperationDefinition:
    """Declare annual projection with a conditional migration commit."""
    return _definition(
        definition_id=MODELO_PROJECT_OPERATION_DEFINITION_ID,
        request_type=ModeloProjectOperationRequest,
        result_type=ModeloProjectOperationProjection,
        executor_type=ModeloProjectExecutor,
        factory=factory,
        migration=migration,
        # The desktop shows a refusal's served words, so the stored detail is released to it.
        public_error_detail=True,
    )


def build_modelo_compare_definition(
    *, factory: CalculationActionPortsFactory, migration: ProjectionMigrationPort
) -> OperationDefinition:
    """Declare comparison with the same guarded full-catalogue migration."""
    return _definition(
        definition_id=MODELO_COMPARE_OPERATION_DEFINITION_ID,
        request_type=ModeloCompareOperationRequest,
        result_type=ModeloCompareOperationProjection,
        executor_type=ModeloCompareExecutor,
        factory=factory,
        migration=migration,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[ModeloProjectOperationRequest] | type[ModeloCompareOperationRequest],
    result_type: type[ModeloProjectOperationProjection] | type[ModeloCompareOperationProjection],
) -> OperationPublicDefinitionRegistrationV1:
    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = require_access_request_payload(
            request, definition_id=definition.definition_id, payload_type=request_type
        )
        # The migration traverses the entire stored revision catalogue, not
        # only the displayed filing years, so each action needs all periods.
        resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
        return replace(
            resolved,
            policy=resolved.policy.model_copy(update={"actions": resolved.policy.actions | {AccessAction.COMMIT}}),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=result_type,
        access_resolver=resolve,
    )


def build_modelo_project_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the annual projection request, result and access contracts."""
    return _registration(
        definition, request_type=ModeloProjectOperationRequest, result_type=ModeloProjectOperationProjection
    )


def build_modelo_compare_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the year comparison request, result and access contracts."""
    return _registration(
        definition, request_type=ModeloCompareOperationRequest, result_type=ModeloCompareOperationProjection
    )


__all__ = [
    "MODELO_COMPARE_OPERATION_DEFINITION_ID",
    "MODELO_PROJECT_OPERATION_DEFINITION_ID",
    "ModeloCompareOperationProjection",
    "ModeloCompareOperationRequest",
    "ModeloProjectOperationProjection",
    "ModeloProjectOperationRequest",
    "ProjectionOverride",
    "build_modelo_compare_definition",
    "build_modelo_compare_registration",
    "build_modelo_project_definition",
    "build_modelo_project_registration",
]
