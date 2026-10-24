"""Registered profile-worker reads behind one declaration's editor workbench.

The workbench screen holds no repository, registry or custody. Every read it
needs runs here, inside the profile worker under the pinned authority, as a
recorded read-only operation whose typed result only a password-authenticated
human session may receive, on any frontend:

- ``modelo.work.form`` reads the editor form, admitting the edit baseline the
  session's parses and applies are judged against;
- ``modelo.work.casilla_help`` assembles one casilla's help;
- ``modelo.edit.renew`` renews a baseline when only its lifetime changed;
- ``modelo.edit.preflight`` checks staged intents without applying them;
- ``modelo.edit.apply_prerequisite`` hands out, once, the calculation source a
  refused Apply named, which the worker retained privately.

None of them writes taxpayer data; each settles with no effect.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.identity.hex_ids import CalculationRevisionId, ModeloEditBaselineId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    OperationBaselinePolicy,
    OperationReplayPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationPublicContractSetV1,
    OperationPublicDefinitionRegistrationV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .casilla_help import ModeloCasillaHelpCardV1
from .edit_admission import ModeloEditRenewedV1, renew_modelo_edit_baseline
from .edit_apply_scalar_contracts import ModeloEditWireScalar, wire_scalar_value
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import (
    ModeloEditCorrectionAddressV1,
    ModeloEditNormalisation,
    ModeloEditParsedValueV1,
    ModeloEditParseRefusalV1,
    ModeloEditParseResultV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusedV1,
    ModeloEditSubmissionV1,
    ModeloEditValueAddressV1,
)
from .edit_operation_requests import ModeloEditPreflightRequestV2
from .edit_parsing import entry_grammar, parse_modelo_edit_lexeme
from .edit_preflight import preflight_modelo_edit
from .edit_prerequisite_wording import read_prerequisite_words
from .edit_refusal_projection import ModeloEditCalculationPrerequisiteV1, ModeloEditRefusalProjectionStore
from .edit_review_wording import (
    ModeloEditReviewFindingV1,
    edit_refusal_words,
    entry_read_back,
    grammar_data_type,
    operator_entries_unknown,
    review_findings,
)
from .edit_transient_operand import modelo_edit_financial_operand
from .edit_value_grammar import ModeloEditValueGrammarV1
from .work_amend_correction import correction_value_grammars
from .work_form_service import modelo_form_snapshot
from .work_lifecycle import get_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .workbench_projection import ModeloWorkbenchFormProjectionV1, project_modelo_workbench_form
from .workbench_read import (
    ModeloWorkbenchReadPortsFactory,
    modelo_edit_prerequisite_source_boxes,
    read_modelo_casilla_help,
    read_modelo_workbench_form,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

MODELO_WORK_FORM_OPERATION_DEFINITION_ID = "modelo.work.form"
MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID = "modelo.work.casilla_help"
MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID = "modelo.edit.renew"
MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID = "modelo.edit.preflight"
MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID = "modelo.edit.apply_prerequisite"

type OperationContractsProvider = Callable[[], OperationPublicContractSetV1]
"""The public contract set of the registry these definitions are composed into."""

_BoundedText = Annotated[str, Field(min_length=1, max_length=128)]


# -- requests -----------------------------------------------------------------


class ModeloWorkbenchFormRequest(CredentialFreeOperationRequest):
    """Exact profile, one declaration and the language its form is read in."""

    profile_id: UUID
    work_unit_id: WorkUnitId
    output_language: OutputLanguage


class ModeloCasillaHelpRequest(CredentialFreeOperationRequest):
    """One casilla of the revision and calculation the workbench form showed."""

    profile_id: UUID
    work_unit_id: WorkUnitId
    casilla_id: CasillaId
    registry_revision_id: _BoundedText
    calculation_revision_id: CalculationRevisionId | None
    output_language: OutputLanguage


class ModeloEditRenewRequest(CredentialFreeOperationRequest):
    """The baseline an edit session holds, to renew before review or submission.

    ``output_language`` is the language a refusal is said in.
    """

    profile_id: UUID
    baseline: ModeloEditApplyBaselineV1
    output_language: OutputLanguage


class ModeloEditApplyPrerequisiteRequest(CredentialFreeOperationRequest):
    """The settled Apply, and the renewed baseline it submitted, whose prerequisite is asked for."""

    profile_id: UUID
    work_unit_id: WorkUnitId
    apply_operation_id: _BoundedText
    baseline_id: ModeloEditBaselineId
    calculation_revision_id: CalculationRevisionId | None
    registry_revision_id: _BoundedText
    #: The language the prerequisite is said in; ``None`` asks for the prerequisite only, for a frontend that
    #: words it from the form it already holds.
    output_language: OutputLanguage | None = None


# -- results ------------------------------------------------------------------


class ModeloCasillaHelpProjectionV1(BaseModel):
    """One casilla's help for an exact profile and declaration."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    card: ModeloCasillaHelpCardV1


class ModeloEditRenewalProjectionV1(BaseModel):
    """The renewed baseline, or the refusal naming what moved; exactly one is present."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    renewed_baseline: ModeloEditApplyBaselineV1 | None
    refusal: ModeloEditRefusedV1 | None
    #: Why the renewal was refused, in the language the request named; ``None`` when it was renewed.
    refusal_words: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_outcome_for_one_declaration(self) -> Self:
        if (self.renewed_baseline is None) == (self.refusal is None):
            raise ValueError("a renewal carries exactly one outcome")
        baseline = self.renewed_baseline
        if baseline is not None and (
            baseline.bucket_id != str(self.profile_id) or baseline.work_unit_id != self.work_unit_id
        ):
            raise ValueError("the renewed baseline belongs to another declaration")
        return self


class ModeloEditTypedEntryV1(BaseModel):
    """One entry as the filer typed it, read through its address's grammar; never the text itself.

    A read entry carries the value in the form an edit intent takes it, with
    what reading it normalised, and reads it back in the entry's language; an
    entry that cannot be read carries why, also in words.
    """

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloEditValueAddressV1
    value: ModeloEditWireScalar = None
    normalisations: tuple[ModeloEditNormalisation, ...] = ()
    refusal: ModeloEditParseRefusalV1 | None = None
    #: The value the entry will be read as, written as its box shows it, in the entry's language.
    value_text: str | None = None
    #: Why the entry cannot be read, as one sentence in the entry's language.
    refusal_words: str | None = None

    @classmethod
    def from_outcome(
        cls, outcome: ModeloEditParseResultV1, *, grammar: ModeloEditValueGrammarV1 | None, language: OutputLanguage
    ) -> ModeloEditTypedEntryV1:
        """Mirror one parse outcome onto the wire, said in ``language``."""
        if isinstance(outcome, ModeloEditParsedValueV1):
            if grammar is None:
                raise TypeError("a read entry was read through its address's grammar")
            return cls(
                address=outcome.address,
                value=wire_scalar_value(outcome.value),
                normalisations=outcome.normalisations,
                value_text=entry_read_back(
                    outcome.value, data_type=grammar_data_type(grammar, outcome.address), language=language
                ),
            )
        refusal = outcome.refusal
        if not isinstance(refusal, ModeloEditParseRefusalV1):
            raise TypeError("an entry is refused only by its address's grammar")
        return cls(address=refusal.address, refusal=refusal, refusal_words=edit_refusal_words(refusal, language))


class ModeloEditPreflightProjectionV1(BaseModel):
    """What checking the staged intents found, naming the address of every finding.

    ``parsed`` reads each entry the submission carried as the filer typed it,
    through its address's grammar: the value it is, with what reading it
    normalised, or why it cannot be read. It is empty when nothing was typed
    and when the submission was refused before anything could be read.

    ``findings`` are the check's findings the review lists, in the request's
    language, and ``refusal_words`` says why the whole check was refused;
    ``operator_entries_unknown`` says whether the filer's earlier entries could
    not be read, which the review says in its own sentence.
    """

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    outcome: Annotated[ModeloEditPreflightEvaluatedV1 | ModeloEditRefusedV1, Field(discriminator="outcome")]
    parsed: tuple[ModeloEditTypedEntryV1, ...] = ()
    findings: tuple[ModeloEditReviewFindingV1, ...] = ()
    operator_entries_unknown: bool = False
    refusal_words: str | None = None


class ModeloEditApplyPrerequisiteV1(BaseModel):
    """The calculation source a refused Apply named, with the earlier-filing boxes it reads."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    calculation_revision_id: str | None
    source_boxes: tuple[CasillaId, ...]
    #: The prerequisite said in the language asked for, one sentence per line; ``None`` when none was asked
    #: for or the form no longer shows the box.
    words: str | None = None


class ModeloEditApplyPrerequisiteProjectionV1(BaseModel):
    """The named prerequisite, consumed by this read, or ``None`` when the Apply named none."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1]
    profile_id: UUID
    work_unit_id: str
    prerequisite: ModeloEditApplyPrerequisiteV1 | None


# -- executors ----------------------------------------------------------------


def _bucket_id(profile_id: UUID) -> str:
    bucket_id = str(profile_id)
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


async def _read[ResultT: BaseModel](
    context: OperationExecutorContext, *, phase: str, task_name: str, read: Callable[[], ResultT]
) -> str:
    """Run one worker read off the event loop and keep its typed result in encrypted custody."""
    await context.events.phase(phase)

    def guarded() -> ResultT:
        with validating_governed_facts(context.authority_operation):
            return read()

    async def capture() -> str:
        result = await asyncio.to_thread(guarded)
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return result_ref

    return await await_cancellation_complete(capture(), task_name=task_name)


def _require_subject(request_definition_id: str, subject_ref: str, definition_id: str, work_unit_id: str) -> None:
    if request_definition_id != definition_id or subject_ref != work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


class ModeloWorkbenchFormExecutor:
    """Read one declaration's form and admit its edit baseline."""

    def __init__(
        self, *, ports_factory: ModeloWorkbenchReadPortsFactory, contracts: OperationContractsProvider
    ) -> None:
        self._ports_factory = ports_factory
        self._contracts = contracts

    async def execute(
        self, request: OperationRequest[ModeloWorkbenchFormRequest], context: OperationExecutorContext
    ) -> str:
        """Read the form under the pinned authority and project it for the exact profile."""
        payload = request.payload
        _require_subject(
            request.definition_id, request.subject_ref, MODELO_WORK_FORM_OPERATION_DEFINITION_ID, payload.work_unit_id
        )
        operation = context.authority_operation

        def read() -> ModeloWorkbenchFormProjectionV1:
            bucket_id = _bucket_id(payload.profile_id)
            form = read_modelo_workbench_form(
                payload.work_unit_id,
                bucket_id=bucket_id,
                ports=self._ports_factory(bucket_id, operation),
                operation=operation,
                operation_contracts=self._contracts(),
                language=payload.output_language,
            )
            return project_modelo_workbench_form(payload.profile_id, payload.work_unit_id, form)

        return await _read(
            context, phase=MODELO_WORK_FORM_OPERATION_DEFINITION_ID, task_name="modelo-work-form-read", read=read
        )


class ModeloCasillaHelpExecutor:
    """Assemble one casilla's help."""

    def __init__(self, *, ports_factory: ModeloWorkbenchReadPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[ModeloCasillaHelpRequest], context: OperationExecutorContext
    ) -> str:
        """Read the help of the revision and calculation the form showed."""
        payload = request.payload
        _require_subject(
            request.definition_id,
            request.subject_ref,
            MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
            payload.work_unit_id,
        )
        operation = context.authority_operation

        def read() -> ModeloCasillaHelpProjectionV1:
            bucket_id = _bucket_id(payload.profile_id)
            card = read_modelo_casilla_help(
                payload.work_unit_id,
                payload.casilla_id,
                bucket_id=bucket_id,
                registry_revision_id=payload.registry_revision_id,
                calculation_revision_id=payload.calculation_revision_id,
                ports=self._ports_factory(bucket_id, operation),
                operation=operation,
                language=payload.output_language,
            )
            return ModeloCasillaHelpProjectionV1(
                result_version=1, profile_id=payload.profile_id, work_unit_id=payload.work_unit_id, card=card
            )

        return await _read(
            context,
            phase=MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
            task_name="modelo-casilla-help-read",
            read=read,
        )


class ModeloEditRenewExecutor:
    """Renew an edit baseline when nothing but its lifetime changed."""

    def __init__(
        self, *, ports_factory: ModeloWorkbenchReadPortsFactory, contracts: OperationContractsProvider
    ) -> None:
        self._ports_factory = ports_factory
        self._contracts = contracts

    async def execute(
        self, request: OperationRequest[ModeloEditRenewRequest], context: OperationExecutorContext
    ) -> str:
        """Re-admit the baseline against live state and report the renewal or what moved."""
        payload = request.payload
        _require_subject(
            request.definition_id,
            request.subject_ref,
            MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
            payload.baseline.work_unit_id,
        )
        operation = context.authority_operation

        def read() -> ModeloEditRenewalProjectionV1:
            bucket_id = _bucket_id(payload.profile_id)
            if payload.baseline.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            ports = self._ports_factory(bucket_id, operation)
            renewal = renew_modelo_edit_baseline(
                payload.baseline.to_baseline(),
                work_catalogue=ports.work_units.load(),
                calculation_catalogue=ports.calculations.load(operation=operation),
                operation=operation,
                operation_contracts=self._contracts(),
            )
            return ModeloEditRenewalProjectionV1(
                result_version=1,
                profile_id=payload.profile_id,
                work_unit_id=payload.baseline.work_unit_id,
                renewed_baseline=(
                    ModeloEditApplyBaselineV1.from_baseline(renewal.baseline)
                    if isinstance(renewal, ModeloEditRenewedV1)
                    else None
                ),
                refusal=renewal if isinstance(renewal, ModeloEditRefusedV1) else None,
                refusal_words=(
                    edit_refusal_words(renewal.refusal, payload.output_language)
                    if isinstance(renewal, ModeloEditRefusedV1)
                    else None
                ),
            )

        return await _read(
            context, phase=MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, task_name="modelo-edit-renew", read=read
        )


def _correction_grammars(
    submission: ModeloEditSubmissionV1, operation: PinnedAuthorityOperation
) -> Mapping[CasillaId, ModeloEditValueGrammarV1] | None:
    """The correction grammars of the baseline's revision, read only when an entry is typed for a correction."""
    if not any(isinstance(lexeme.address, ModeloEditCorrectionAddressV1) for lexeme in submission.lexemes):
        return None
    baseline = submission.baseline
    return correction_value_grammars(
        modelo_form_snapshot(
            operation, baseline.modelo, baseline.filing_year, baseline.period, baseline.law_selected_revision_id
        )
    )


class ModeloEditPreflightExecutor:
    """Check staged intents against the declaration without applying them."""

    def __init__(self, *, ports_factory: ModeloWorkbenchReadPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[ModeloEditPreflightRequestV2], context: OperationExecutorContext
    ) -> str:
        """Evaluate every intent and the resulting required casillas, naming each finding's address."""
        payload = request.payload
        _require_subject(
            request.definition_id,
            request.subject_ref,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            payload.work_unit_id,
        )
        operation = context.authority_operation

        def read(submission: ModeloEditSubmissionV1) -> ModeloEditPreflightProjectionV1:
            baseline = submission.baseline
            bucket_id = _bucket_id(payload.profile_id)
            if baseline.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            ports = self._ports_factory(bucket_id, operation)
            tax_id_format = runtime_tax_id_format(authority=operation)
            outcome = preflight_modelo_edit(
                submission,
                work_catalogue=ports.work_units.load(),
                calculation_catalogue=ports.calculations.load(operation=operation),
                tax_id_format=tax_id_format,
            )
            corrections = _correction_grammars(submission, operation)
            parsed = (
                ()
                if isinstance(outcome, ModeloEditRefusedV1)
                else tuple(
                    ModeloEditTypedEntryV1.from_outcome(
                        parse_modelo_edit_lexeme(
                            lexeme, baseline=baseline, tax_id_format=tax_id_format, correction_grammars=corrections
                        ),
                        grammar=entry_grammar(lexeme.address, baseline=baseline, correction_grammars=corrections),
                        language=lexeme.entry_locale,
                    )
                    for lexeme in submission.lexemes
                )
            )
            language = payload.output_language
            refused = outcome.refusal if isinstance(outcome, ModeloEditRefusedV1) else None
            found = () if isinstance(outcome, ModeloEditRefusedV1) else outcome.findings
            return ModeloEditPreflightProjectionV1(
                result_version=1,
                profile_id=payload.profile_id,
                work_unit_id=baseline.work_unit_id,
                outcome=outcome,
                parsed=parsed,
                findings=review_findings(found, language),
                operator_entries_unknown=operator_entries_unknown(found),
                refusal_words=None if refused is None else edit_refusal_words(refused, language),
            )

        async with context.typed_financial_operand.consume(ModeloEditSubmissionV1) as submission:
            try:
                return await _read(
                    context,
                    phase=MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
                    task_name="modelo-edit-preflight",
                    read=lambda operand=submission: read(operand),
                )
            finally:
                del submission


class ModeloEditApplyPrerequisiteExecutor:
    """Hand out, once, the prerequisite a refused Apply named in this worker."""

    def __init__(
        self, *, ports_factory: ModeloWorkbenchReadPortsFactory, store: ModeloEditRefusalProjectionStore
    ) -> None:
        self._ports_factory = ports_factory
        self._store = store

    def _named(
        self,
        prerequisite: ModeloEditCalculationPrerequisiteV1,
        payload: ModeloEditApplyPrerequisiteRequest,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> ModeloEditApplyPrerequisiteV1:
        ports = self._ports_factory(bucket_id, operation)
        boxes = modelo_edit_prerequisite_source_boxes(
            prerequisite,
            bucket_id=bucket_id,
            registry_revision_id=payload.registry_revision_id,
            ports=ports,
            operation=operation,
        )
        language = payload.output_language
        words = (
            None
            if language is None
            else read_prerequisite_words(
                payload.work_unit_id,
                prerequisite.casilla_id,
                boxes,
                bucket_id=bucket_id,
                ports=ports,
                operation=operation,
                language=language,
            )
        )
        return ModeloEditApplyPrerequisiteV1(
            casilla_id=prerequisite.casilla_id,
            calculation_revision_id=prerequisite.calculation_revision_id,
            source_boxes=boxes,
            words=words,
        )

    async def execute(
        self, request: OperationRequest[ModeloEditApplyPrerequisiteRequest], context: OperationExecutorContext
    ) -> str:
        """Consume the retained prerequisite matching the Apply's exact coordinates."""
        payload = request.payload
        _require_subject(
            request.definition_id,
            request.subject_ref,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            payload.work_unit_id,
        )
        operation = context.authority_operation

        def read() -> ModeloEditApplyPrerequisiteProjectionV1:
            bucket_id = _bucket_id(payload.profile_id)
            prerequisite = self._store.take(
                payload.apply_operation_id,
                work_unit_id=payload.work_unit_id,
                baseline_id=payload.baseline_id,
                calculation_revision_id=payload.calculation_revision_id,
            )
            named = None if prerequisite is None else self._named(prerequisite, payload, bucket_id, operation)
            return ModeloEditApplyPrerequisiteProjectionV1(
                result_version=1, profile_id=payload.profile_id, work_unit_id=payload.work_unit_id, prerequisite=named
            )

        return await _read(
            context,
            phase=MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            task_name="modelo-edit-apply-prerequisite",
            read=read,
        )


# -- definitions --------------------------------------------------------------


_READ_CAPABILITIES = RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
#: Four of the reads name their declaration directly; the renewal names it inside the baseline it renews.
_WORK_UNIT_SUBJECT = OperationSubjectReferenceV1.payload_field("work_unit_id")
#: Each read's public request and result models, in registration order.
_SCHEMAS: Final[Mapping[str, tuple[type[BaseModel], type[BaseModel]]]] = MappingProxyType(
    {
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID: (ModeloWorkbenchFormRequest, ModeloWorkbenchFormProjectionV1),
        MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID: (ModeloCasillaHelpRequest, ModeloCasillaHelpProjectionV1),
        MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID: (ModeloEditRenewRequest, ModeloEditRenewalProjectionV1),
        MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID: (ModeloEditPreflightRequestV2, ModeloEditPreflightProjectionV1),
        MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID: (
            ModeloEditApplyPrerequisiteRequest,
            ModeloEditApplyPrerequisiteProjectionV1,
        ),
    }
)


def _definition(
    definition_id: str,
    request_type: type[CredentialFreeOperationRequest],
    subject_reference: OperationSubjectReferenceV1,
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=subject_reference,
        result_type=result_type,
        executor_type=executor_type,
        build=build,
        capabilities=_READ_CAPABILITIES
        if definition_id != MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID
        else _READ_CAPABILITIES.model_copy(
            update={"replay": OperationReplayPolicy.NONE, "baseline": OperationBaselinePolicy.EXACT_APPROVAL}
        ),
        transient_financial_operand=modelo_edit_financial_operand(None)
        if definition_id == MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID
        else None,
    )


def build_modelo_workbench_operation_definitions(
    *,
    ports_factory: ModeloWorkbenchReadPortsFactory,
    contracts: OperationContractsProvider,
    prerequisites: ModeloEditRefusalProjectionStore,
) -> tuple[OperationDefinition, ...]:
    """Bind the workbench's five worker reads to the profile repositories and this registry's contracts."""
    return (
        _definition(
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest,
            _WORK_UNIT_SUBJECT,
            ModeloWorkbenchFormProjectionV1,
            ModeloWorkbenchFormExecutor,
            lambda: ModeloWorkbenchFormExecutor(ports_factory=ports_factory, contracts=contracts),
        ),
        _definition(
            MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
            ModeloCasillaHelpRequest,
            _WORK_UNIT_SUBJECT,
            ModeloCasillaHelpProjectionV1,
            ModeloCasillaHelpExecutor,
            lambda: ModeloCasillaHelpExecutor(ports_factory=ports_factory),
        ),
        _definition(
            MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
            ModeloEditRenewRequest,
            OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"),
            ModeloEditRenewalProjectionV1,
            ModeloEditRenewExecutor,
            lambda: ModeloEditRenewExecutor(ports_factory=ports_factory, contracts=contracts),
        ),
        _definition(
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditPreflightRequestV2,
            _WORK_UNIT_SUBJECT,
            ModeloEditPreflightProjectionV1,
            ModeloEditPreflightExecutor,
            lambda: ModeloEditPreflightExecutor(ports_factory=ports_factory),
        ),
        _definition(
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            ModeloEditApplyPrerequisiteRequest,
            _WORK_UNIT_SUBJECT,
            ModeloEditApplyPrerequisiteProjectionV1,
            ModeloEditApplyPrerequisiteExecutor,
            lambda: ModeloEditApplyPrerequisiteExecutor(ports_factory=ports_factory, store=prerequisites),
        ),
    )


def build_modelo_workbench_operation_registrations(
    definitions: tuple[OperationDefinition, ...], *, access_resolver: OperationAccessResolver
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Expose each read's exact request and result through version-one public schemas."""
    if tuple(definition.definition_id for definition in definitions) != tuple(_SCHEMAS):
        raise ValueError("wrong modelo workbench definitions")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=_SCHEMAS[definition.definition_id][1],
            request_schema_version=2
            if definition.definition_id == MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID
            else 1,
            access_resolver=access_resolver,
        )
        for definition in definitions
    )


# -- access -------------------------------------------------------------------


def _addressed_work_unit(request: OperationRequest[BaseModel], context: OperationAccessContext) -> str:
    """The declaration a workbench request addresses, refusing a request for another profile."""
    payload = request.payload
    if isinstance(payload, ModeloWorkbenchFormRequest | ModeloCasillaHelpRequest | ModeloEditApplyPrerequisiteRequest):
        profile_id, work_unit_id = payload.profile_id, payload.work_unit_id
    elif isinstance(payload, ModeloEditRenewRequest):
        if payload.baseline.bucket_id != str(context.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        profile_id, work_unit_id = payload.profile_id, payload.baseline.work_unit_id
    elif isinstance(payload, ModeloEditPreflightRequestV2):
        profile_id, work_unit_id = payload.profile_id, payload.work_unit_id
    else:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if profile_id != context.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if request.subject_ref != work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return work_unit_id


def compose_modelo_workbench_access(ports_factory: ActiveWorkLifecyclePortsFactory) -> OperationAccessResolver:
    """Scope every workbench read to the persisted declaration it addresses and to a live human session."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        work_unit_id = _addressed_work_unit(request, context)
        ports = ports_factory()
        if ports.work_unit_repository.bucket_id != str(context.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        unit = get_work_unit(work_unit_id, ports=ports)
        if unit.bucket_id != str(context.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        periods = frozenset({unit.period})
        disclosures = frozenset[DisclosurePermission]()
        if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        elif context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                DisclosurePermission(
                    destination_id=context.destination_id, projection_id=schema.schema_id, category=category
                )
                for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=False,
                destination_id=context.destination_id,
            ),
            policy=OperationAccessPolicy(
                definition_id=request.definition_id,
                definition_contract_digest=context.contract.definition_contract_digest,
                actions=frozenset(
                    {
                        AccessAction.SUBMIT,
                        AccessAction.START,
                        AccessAction.RESUME,
                        AccessAction.COMMIT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                    }
                ),
                disclosures=disclosures,
                periods=periods,
                allow_period_independent=False,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
                requires_human=True,
            ),
        )

    return resolve


__all__ = [
    "MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID",
    "MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID",
    "MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID",
    "MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID",
    "MODELO_WORK_FORM_OPERATION_DEFINITION_ID",
    "ModeloCasillaHelpProjectionV1",
    "ModeloCasillaHelpRequest",
    "ModeloEditApplyPrerequisiteProjectionV1",
    "ModeloEditApplyPrerequisiteRequest",
    "ModeloEditApplyPrerequisiteV1",
    "ModeloEditPreflightProjectionV1",
    "ModeloEditRenewRequest",
    "ModeloEditRenewalProjectionV1",
    "ModeloEditTypedEntryV1",
    "ModeloWorkbenchFormRequest",
    "OperationContractsProvider",
    "build_modelo_workbench_operation_definitions",
    "build_modelo_workbench_operation_registrations",
    "compose_modelo_workbench_access",
]
