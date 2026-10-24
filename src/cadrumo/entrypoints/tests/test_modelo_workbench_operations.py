"""The workbench's worker reads run their production executors over real encrypted storage.

Each executor runs as the profile worker runs it -- under the pinned authority,
against the profile's repositories -- and hands its typed public result to
operand custody, which is kept in memory here. The supervisor, journal and
transport around them are proven by the registered-executor and native runtime
suites. Every result is shown to survive the registered result schema as JSON
and to restore the canonical read it was projected from.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.entrypoints.tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.modelo.action_errors import ModeloEditBaselineStaleError
from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ...application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditApplyRequestV1,
    ModeloEditCorrectionAddressV1,
    ModeloEditHeldChangeV1,
    ModeloEditHeldKind,
    ModeloEditParseReason,
    ModeloEditParseRequestV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_operation_requests import ModeloEditPreflightRequestV2
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
from ...application.modelo.edit_parse_text import parse_refusal_text
from ...application.modelo.edit_preflight import VALUE_REFUSED_PREFIX
from ...application.modelo.edit_refusal_projection import (
    ModeloEditCalculationPrerequisiteV1,
    ModeloEditRefusalProjectionStore,
)
from ...application.modelo.edit_review_wording import STATED_BY_THE_REVIEW
from ...application.modelo.edit_transient_operand import modelo_edit_financial_operand
from ...application.modelo.value_presentation import format_casilla_value
from ...application.modelo.work_amend_contracts import ModeloWorkAmendOverride
from ...application.modelo.work_form_models import ModeloFormCasillaAddressV1, comparable_entry
from ...application.modelo.work_form_rebase import ModeloFormRebaseOutcome, held_change
from ...application.modelo.work_form_service import load_modelo_work_form
from ...application.modelo.workbench_operations import (
    MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
    MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloCasillaHelpExecutor,
    ModeloCasillaHelpProjectionV1,
    ModeloCasillaHelpRequest,
    ModeloEditApplyPrerequisiteExecutor,
    ModeloEditApplyPrerequisiteProjectionV1,
    ModeloEditApplyPrerequisiteRequest,
    ModeloEditPreflightExecutor,
    ModeloEditPreflightProjectionV1,
    ModeloEditRenewalProjectionV1,
    ModeloEditRenewExecutor,
    ModeloEditRenewRequest,
    ModeloWorkbenchFormExecutor,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1, restore_modelo_workbench_form
from ...application.modelo.workbench_read import ModeloWorkbenchReadPorts, read_modelo_workbench_form
from ...application.operations.financial_operand_contract import (
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
)
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.tests.financial_operand_delivery import deliver_financial_operand
from ...application.operations.typed_financial_operand_context import BoundTypedFinancialOperandAccess
from ...core.casilla_id import validated_casilla_id
from ...core.errors.error_codes import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.i18n.render import tr
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..adapter_composition import build_calculation_action_ports
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


class _Executor(Protocol):
    async def execute(self, request: Any, context: OperationExecutorContext) -> str: ...


class _OperationLoadRepository(Protocol):
    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> Any: ...


@dataclass(slots=True)
class _Events:
    phases: list[str] = field(default_factory=list)
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


@dataclass(slots=True)
class _Operands:
    results: list[BaseModel] = field(default_factory=list)

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.results.append(operand)
        return content_hash_hex({"operand": len(self.results)})


@dataclass(frozen=True, slots=True)
class _Context:
    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: _Events = field(default_factory=_Events)
    cancellation: _Cancellation = field(default_factory=_Cancellation)
    operands: _Operands = field(default_factory=_Operands)
    typed_financial_operand: BoundTypedFinancialOperandAccess = field(
        default_factory=lambda: BoundTypedFinancialOperandAccess(broker=None, declaration=None, requirement=None)
    )


def _run[ResultT: BaseModel](
    work: SeededOperatorWork,
    executor: _Executor,
    definition_id: str,
    payload: BaseModel,
    result_type: type[ResultT],
    *,
    input_json: str | None = None,
) -> tuple[ResultT, _Context]:
    """Run one executor as the worker does, and prove its result survives its public JSON form.

    ``input_json`` is the operator input exactly as a frontend sends it, when
    it carries what no dump repeats, such as entries as the filer typed them.
    """
    context = _Context(
        identity=OperationIdentity(
            operation_id=content_hash_hex({"read": definition_id}),
            definition_id=definition_id,
            subject_ref=work.work_unit_id,
        ),
        authority_operation=work.operation,
    )
    request = OperationRequest(definition_id=definition_id, subject_ref=work.work_unit_id, payload=payload)

    async def execute() -> None:
        nonlocal context
        if isinstance(payload, ModeloEditOperatorInputV2):
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=UUID(work.work_unit.bucket_id),
                subject_ref=work.work_unit_id,
                input_json=payload.model_dump_json() if input_json is None else input_json,
            )
            try:
                assert prepared.operand is not None
                async with deliver_financial_operand(
                    identity=context.identity,
                    declaration=modelo_edit_financial_operand(None),
                    operand=prepared.operand,
                ) as access:
                    prepared.release()
                    context = replace(context, typed_financial_operand=access)
                    await executor.execute(
                        OperationRequest(
                            definition_id=definition_id, subject_ref=work.work_unit_id, payload=prepared.request
                        ),
                        cast(OperationExecutorContext, context),
                    )
            finally:
                prepared.release()
        else:
            await executor.execute(request, cast(OperationExecutorContext, context))

    asyncio.run(execute())
    (result,) = context.operands.results
    assert isinstance(result, result_type)
    assert result_type.model_validate_json(result.model_dump_json()) == result
    assert context.events.phases == [definition_id]
    assert context.events.effects == [OperationEffect.NONE]
    return result, context


def _profile_id(work: SeededOperatorWork) -> UUID:
    return UUID(work.work_unit.bucket_id)


@dataclass(slots=True)
class _OperationLoadObservations:
    calculations: list[PinnedAuthorityOperation | None] = field(default_factory=list)
    verifications: list[PinnedAuthorityOperation | None] = field(default_factory=list)


def _observe_repository_load(
    repository: _OperationLoadRepository,
    observed_operations: list[PinnedAuthorityOperation | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_load = repository.load

    def observe(*, operation: PinnedAuthorityOperation | None = None) -> Any:
        observed_operations.append(operation)
        return original_load(operation=operation)

    monkeypatch.setattr(repository, "load", observe)


def _assert_held_operation(
    observed_operations: list[PinnedAuthorityOperation | None],
    operation: PinnedAuthorityOperation,
) -> None:
    assert observed_operations
    assert all(observed is operation for observed in observed_operations)


def _workbench_read_ports(
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    *,
    observations: _OperationLoadObservations | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> ModeloWorkbenchReadPorts:
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    verifications = VerificationReportCatalogueRepository(bucket_id=bucket_id)
    if observations is not None:
        assert monkeypatch is not None
        _observe_repository_load(ports.calculation_repository, observations.calculations, monkeypatch)
        _observe_repository_load(verifications, observations.verifications, monkeypatch)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=verifications,
        bucket_events=ports.bucket_event_repository,
    )


def _ports_factory(
    work: SeededOperatorWork,
    *,
    observations: _OperationLoadObservations | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
):
    return lambda bucket_id, operation: _workbench_read_ports(
        bucket_id, operation, observations=observations, monkeypatch=monkeypatch
    )


def test_the_form_read_admits_an_edit_and_restores_the_exact_application_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        observations = _OperationLoadObservations()
        contracts = build_production_operation_registry().public_contract_set
        executor = ModeloWorkbenchFormExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch),
            contracts=lambda: contracts,
        )
        projection, _context = _run(
            work,
            executor,
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest(
                profile_id=_profile_id(work), work_unit_id=work.work_unit_id, output_language=OutputLanguage.EN
            ),
            ModeloWorkbenchFormProjectionV1,
        )
        assert len(observations.calculations) == 2
        restored = restore_modelo_workbench_form(
            ModeloWorkbenchFormProjectionV1.model_validate_json(projection.model_dump_json())
        )
        direct = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=_workbench_read_ports(
                work.work_unit.bucket_id,
                work.operation,
                observations=observations,
                monkeypatch=monkeypatch,
            ),
            operation=work.operation,
            operation_contracts=contracts,
            language=OutputLanguage.EN,
        )
        _assert_held_operation(observations.calculations, work.operation)
        _assert_held_operation(observations.verifications, work.operation)
        assert len(observations.calculations) == 4
        standalone = load_modelo_work_form(
            work.work_unit.bucket_id,
            work.work_unit.modelo,
            work.work_unit.filing_year,
            work.work_unit.period,
            operation=work.operation,
            work_unit_repository=work.ports.work_unit_repository,
            calculation_repository=work.ports.calculation_repository,
            verification_repository=VerificationReportCatalogueRepository(bucket_id=work.work_unit.bucket_id),
            admission=direct.admission,
            language=OutputLanguage.EN,
            bucket_events=work.ports.bucket_event_repository,
        )

    assert projection.admitted_baseline is not None and projection.admission_refusal is None
    assert isinstance(restored.admission, ModeloEditAdmittedV1)
    assert restored.load == direct.load
    assert direct.load == standalone
    assert restored.calculation_revision_id == direct.calculation_revision_id
    assert restored.tax_id_format == direct.tax_id_format
    tampered = projection.model_copy(
        update={
            "admitted_baseline": projection.admitted_baseline.model_copy(
                update={"bucket_id": "13000000-0000-4000-8000-000000000999"}
            )
        }
    )
    with pytest.raises(ValidationError, match="admitted baseline belongs to another declaration"):
        ModeloWorkbenchFormProjectionV1.model_validate_json(tampered.model_dump_json())


def test_an_uncalculated_form_keeps_one_encrypted_catalogue_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with seeded_operator_work(tmp_path) as work:
        observations = _OperationLoadObservations()
        result = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=_workbench_read_ports(
                work.work_unit.bucket_id, work.operation, observations=observations, monkeypatch=monkeypatch
            ),
            operation=work.operation,
            operation_contracts=build_production_operation_registry().public_contract_set,
            language=OutputLanguage.EN,
        )

    assert result.calculation_revision_id is None
    assert result.load.form.operator_entries_known
    assert observations.calculations == [work.operation]


def test_the_form_keeps_its_final_encrypted_parent_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        ports = _workbench_read_ports(work.work_unit.bucket_id, work.operation)
        original_load = ports.calculations.load
        reads = 0

        def read_with_parent_removed(
            *, operation: PinnedAuthorityOperation | None = None
        ) -> CalculationRevisionCatalogue:
            nonlocal reads
            reads += 1
            if reads == 2:
                ports.work_units.save(WorkUnitCatalogue())
            return original_load(operation=operation)

        monkeypatch.setattr(ports.calculations, "load", read_with_parent_removed)
        with pytest.raises(CalculationRevisionPersistenceError) as refused:
            read_modelo_workbench_form(
                work.work_unit_id,
                bucket_id=work.work_unit.bucket_id,
                ports=ports,
                operation=work.operation,
                operation_contracts=build_production_operation_registry().public_contract_set,
                language=OutputLanguage.EN,
            )

    assert reads == 2
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "missing_parent_work_unit"


def test_casilla_help_is_read_for_the_revision_and_calculation_the_form_showed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        observations = _OperationLoadObservations()
        executor = ModeloCasillaHelpExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch)
        )
        projection, _context = _run(
            work,
            executor,
            MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
            ModeloCasillaHelpRequest(
                profile_id=_profile_id(work),
                work_unit_id=work.work_unit_id,
                casilla_id=validated_casilla_id("06"),
                registry_revision_id=str(work.work_unit.revision_id),
                calculation_revision_id=head.calculation_revision_id,
                output_language=OutputLanguage.EN,
            ),
            ModeloCasillaHelpProjectionV1,
        )
        _assert_held_operation(observations.calculations, work.operation)

    assert projection.card.casilla_id == "06"
    assert projection.work_unit_id == work.work_unit_id


def test_renewal_extends_an_unmoved_baseline_and_names_what_moved_otherwise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        contracts = build_production_operation_registry().public_contract_set
        observations = _OperationLoadObservations()
        executor = ModeloEditRenewExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch),
            contracts=lambda: contracts,
        )
        expired = work.admit(issued_at=datetime.now(UTC) - timedelta(minutes=10))
        assert isinstance(expired, ModeloEditAdmittedV1)
        request = ModeloEditRenewRequest(
            profile_id=_profile_id(work),
            baseline=ModeloEditApplyBaselineV1.from_baseline(expired.baseline),
            output_language=OutputLanguage.EN,
        )
        renewed, _ = _run(
            work, executor, MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, request, ModeloEditRenewalProjectionV1
        )
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )
        moved, _ = _run(
            work, executor, MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, request, ModeloEditRenewalProjectionV1
        )
        _assert_held_operation(observations.calculations, work.operation)

    assert renewed.renewed_baseline is not None and renewed.refusal is None
    assert renewed.renewed_baseline.expires_at > datetime.now(UTC)
    assert moved.renewed_baseline is None and moved.refusal is not None
    assert isinstance(moved.refusal.refusal, ModeloEditStaleBaselineRefusalV1)
    # The refusal is said in the language the request named, in its registered family's message.
    assert renewed.refusal_words is None
    assert moved.refusal_words == resolve_error_message(ModeloEditBaselineStaleError(), locale=OutputLanguage.EN.value)


def test_preflight_names_the_address_of_its_findings_without_applying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        before = work.recalculate()
        observations = _OperationLoadObservations()
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        submission = ModeloEditSubmissionV1(
            baseline=admission.baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, scalar_intents=(_SET_06,)
        )
        executor = ModeloEditPreflightExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch),
            contracts=lambda: build_production_operation_registry().public_contract_set,
        )
        projection, _ = _run(
            work,
            executor,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
            ModeloEditPreflightProjectionV1,
        )
        after = work.require_head()
        _assert_held_operation(observations.calculations, work.operation)

    assert isinstance(projection.outcome, ModeloEditPreflightEvaluatedV1)
    assert all(finding.address in {None, _SET_06.address} for finding in projection.outcome.findings)
    assert after.calculation_revision_id == before.calculation_revision_id
    listed = [finding for finding in projection.outcome.findings if finding.code not in STATED_BY_THE_REVIEW]
    assert [finding.code for finding in projection.findings] == [finding.code for finding in listed]
    for worded in projection.findings:
        if not worded.code.startswith(VALUE_REFUSED_PREFIX):
            assert worded.words == tr(f"workspace.modelo.review.finding.{worded.code}", locale=OutputLanguage.EN.value)
    assert projection.refusal_words is None


def _typed_input(submission: ModeloEditSubmissionV1, typed: tuple[str, ...]) -> str:
    """The operator input a frontend sends: the submission, with each entry's text as the filer typed it."""
    document = json.loads(
        ModeloEditOperatorInputV2(
            submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
        ).model_dump_json()
    )
    for entry, text in zip(document["submission"]["lexemes"], typed, strict=True):
        entry["lexeme"] = text
    return json.dumps(document)


def test_preflight_reads_each_entry_as_typed_through_its_address_grammar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Spanish amount reads as its value, nonsense and a box nobody may write are refused, nothing applied."""
    with seeded_operator_work(tmp_path) as work:
        before = work.recalculate()
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        writable = {
            entry.casilla_id
            for entry in admission.baseline.permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
        }
        revision = work.operation.revision_for_context("130", filing_year=2026, period="1T")
        closed = next(casilla.id for casilla in revision.casillas if casilla.id not in writable)
        entries = (
            ModeloEditParseRequestV1(address=_SET_06.address, entry_locale=OutputLanguage.ES, lexeme=""),
            ModeloEditParseRequestV1(
                address=ModeloEditScalarAddressV1(casilla_id=closed), entry_locale=OutputLanguage.ES, lexeme=""
            ),
        )
        submission = ModeloEditSubmissionV1(
            baseline=admission.baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, lexemes=entries
        )
        executor = ModeloEditPreflightExecutor(
            ports_factory=_ports_factory(work, observations=_OperationLoadObservations(), monkeypatch=monkeypatch),
            contracts=lambda: build_production_operation_registry().public_contract_set,
        )
        projection, _ = _run(
            work,
            executor,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
            ModeloEditPreflightProjectionV1,
            input_json=_typed_input(submission, ("1.234,56", "7")),
        )
        nonsense, _ = _run(
            work,
            executor,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(
                    submission.model_copy(update={"lexemes": entries[:1]})
                ),
                output_language=OutputLanguage.EN,
            ),
            ModeloEditPreflightProjectionV1,
            input_json=_typed_input(submission.model_copy(update={"lexemes": entries[:1]}), ("doce",)),
        )
        after = work.require_head()

    assert isinstance(projection.outcome, ModeloEditPreflightEvaluatedV1)
    amount, closed_box = projection.parsed
    assert (amount.address, amount.value, amount.refusal) == (_SET_06.address, "1234.56", None)
    assert closed_box.refusal is not None
    assert closed_box.refusal.reason is ModeloEditParseReason.ADDRESS_NOT_WRITABLE
    (word,) = nonsense.parsed
    assert word.value is None and word.refusal is not None and word.refusal.address == _SET_06.address
    # Each entry is read back, or refused, in the language it was typed in.
    six = next(
        entry
        for entry in admission.baseline.permitted_surface
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == _SET_06.address.casilla_id
    )
    assert amount.value_text == format_casilla_value(
        Decimal("1234.56"), data_type=six.grammar.data_type, language=OutputLanguage.ES
    )
    assert amount.refusal_words is None
    # The entry compares as a figure, the form a box's own value takes, so "1.234,560" would compare equal too.
    assert amount.comparable_value == comparable_entry(Decimal("1234.560")) == "1234.56"
    assert closed_box.comparable_value is None
    assert closed_box.refusal_words == parse_refusal_text(closed_box.refusal, OutputLanguage.ES)
    assert word.refusal_words == parse_refusal_text(word.refusal, OutputLanguage.ES)
    # What the filer typed never comes back, only the value it is read as, and nothing was applied.
    read_back = {"parsed": {"__all__": {"value_text"}}}
    assert "1.234,56" not in projection.model_dump_json(exclude=read_back) and "doce" not in nonsense.model_dump_json()
    assert after.calculation_revision_id == before.calculation_revision_id


def test_an_apply_carrying_entries_as_typed_is_refused_before_it_is_admitted(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        submission = ModeloEditSubmissionV1(
            baseline=admission.baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            lexemes=(ModeloEditParseRequestV1(address=_SET_06.address, entry_locale=OutputLanguage.ES, lexeme=""),),
        )
        with pytest.raises(OperationFinancialOperandRefusedError) as refused:
            prepare_modelo_edit_operand(
                definition_id="modelo.edit.apply",
                profile_id=UUID(work.work_unit.bucket_id),
                subject_ref=work.work_unit_id,
                input_json=_typed_input(submission, ("100",)),
            )
        with pytest.raises(ValidationError):
            ModeloEditApplyRequestV1(operation_id="a" * 64, submission=submission)

    assert refused.value.reason is OperationFinancialOperandRefusalCode.ENTRY_AS_TYPED


def test_a_retained_prerequisite_is_handed_out_once_to_its_exact_apply(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        store = ModeloEditRefusalProjectionStore()
        prerequisite = ModeloEditCalculationPrerequisiteV1(
            operation_id="d" * 64,
            work_unit_id=work.work_unit_id,
            baseline_id="b" * 64,
            calculation_revision_id=head.calculation_revision_id,
            casilla_id=validated_casilla_id("06"),
            binding_ids=(),
        )
        store.retain(prerequisite)
        executor = ModeloEditApplyPrerequisiteExecutor(ports_factory=_ports_factory(work), store=store)
        request = ModeloEditApplyPrerequisiteRequest(
            profile_id=_profile_id(work),
            work_unit_id=work.work_unit_id,
            apply_operation_id="d" * 64,
            baseline_id="b" * 64,
            calculation_revision_id=head.calculation_revision_id,
            registry_revision_id=str(work.work_unit.revision_id),
        )
        first, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request,
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        second, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request,
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        store.retain(prerequisite)
        worded, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request.model_copy(update={"output_language": OutputLanguage.ES}),
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        store.retain(replace(prerequisite, operation_id="e" * 64))
        other_baseline, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request.model_copy(update={"apply_operation_id": "e" * 64, "baseline_id": "c" * 64}),
            ModeloEditApplyPrerequisiteProjectionV1,
        )

    assert first.prerequisite is not None
    assert first.prerequisite.casilla_id == "06"
    assert first.prerequisite.calculation_revision_id == head.calculation_revision_id
    assert first.prerequisite.words is None
    assert worded.prerequisite is not None and worded.prerequisite.words is not None
    assert worded.prerequisite.words.splitlines()[0] in {
        tr("workspace.modelo.apply_prerequisite.what", locale="es"),
        tr("workspace.modelo.apply_prerequisite.earlier", locale="es"),
    }
    assert second.prerequisite is None
    assert other_baseline.prerequisite is None


def test_preflight_reads_a_correction_typed_for_any_box_the_revision_defines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A corrected figure reads for a box no edit may write, through the correction grammar, and nothing is applied."""
    with seeded_operator_work(tmp_path) as work:
        before = work.recalculate()
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        writable = {
            entry.casilla_id
            for entry in admission.baseline.permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
        }
        revision = work.operation.revision_for_context("130", filing_year=2026, period="1T")
        closed = next(casilla.id for casilla in revision.casillas if casilla.id not in writable)
        entries = (
            ModeloEditParseRequestV1(
                address=ModeloEditCorrectionAddressV1(casilla_id=closed), entry_locale=OutputLanguage.ES, lexeme=""
            ),
            ModeloEditParseRequestV1(
                address=ModeloEditCorrectionAddressV1(casilla_id=validated_casilla_id("06")),
                entry_locale=OutputLanguage.ES,
                lexeme="",
            ),
        )
        submission = ModeloEditSubmissionV1(
            baseline=admission.baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, lexemes=entries
        )
        executor = ModeloEditPreflightExecutor(
            ports_factory=_ports_factory(work, observations=_OperationLoadObservations(), monkeypatch=monkeypatch),
            contracts=lambda: build_production_operation_registry().public_contract_set,
        )
        projection, _ = _run(
            work,
            executor,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
            ModeloEditPreflightProjectionV1,
            input_json=_typed_input(submission, ("1.234,567", "1,1234567")),
        )
        after = work.require_head()

    assert isinstance(projection.outcome, ModeloEditPreflightEvaluatedV1)
    corrected, too_fine = projection.parsed
    assert (corrected.address, corrected.value, corrected.refusal) == (entries[0].address, "1234.567", None)
    ModeloWorkAmendOverride(casilla_id=closed, value="1234.567")
    assert too_fine.refusal is not None
    assert too_fine.refusal.reason is ModeloEditParseReason.TOO_MANY_DECIMALS
    assert "1.234,567" not in projection.model_dump_json(exclude={"parsed": {"__all__": {"value_text"}}})
    assert after.calculation_revision_id == before.calculation_revision_id


def test_preflight_reports_what_becomes_of_each_held_change_by_its_box(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A held change on a box that moved reads as changed, one on a box the form no longer has as dropped.

    The held changes travel inside the preflight's transient submission only: the journaled request has no
    place for them, and the result says what became of each without the box's state digest.
    """
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        contracts = build_production_operation_registry().public_contract_set
        observations = _OperationLoadObservations()
        ports_factory = _ports_factory(work, observations=observations, monkeypatch=monkeypatch)
        read, _ = _run(
            work,
            ModeloWorkbenchFormExecutor(ports_factory=ports_factory, contracts=lambda: contracts),
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest(
                profile_id=_profile_id(work), work_unit_id=work.work_unit_id, output_language=OutputLanguage.EN
            ),
            ModeloWorkbenchFormProjectionV1,
        )
        form = restore_modelo_workbench_form(read).load.form
        box = next(
            field
            for field in form.fields()
            if field.address == ModeloFormCasillaAddressV1(casilla_id=_SET_06.address.casilla_id)
        )
        assert box.takes_typed_value
        mine = held_change(box, ModeloEditHeldKind.SET)
        gone = ModeloEditHeldChangeV1(
            address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("999")),
            kind=ModeloEditHeldKind.SET,
            held_state=box.state_digest,
        )
        assert read.admitted_baseline is not None
        baseline = read.admitted_baseline.to_baseline()
        submission = ModeloEditSubmissionV1(
            baseline=baseline, mutation_family=baseline.mutation_family, held=(mine, gone)
        )
        payload = ModeloEditOperatorInputV2(
            submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
        )
        executor = ModeloEditPreflightExecutor(ports_factory=ports_factory, contracts=lambda: contracts)
        unmoved, _ = _run(
            work, executor, MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID, payload, ModeloEditPreflightProjectionV1
        )
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            clock=SEEDED_AT,
            casilla_inputs={box.address.casilla_id: Decimal("100")},
        )
        stale, _ = _run(
            work, executor, MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID, payload, ModeloEditPreflightProjectionV1
        )
        # Read again, the declaration admits a fresh baseline; the changes held from the first read go with it.
        reread, _ = _run(
            work,
            ModeloWorkbenchFormExecutor(ports_factory=ports_factory, contracts=lambda: contracts),
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest(
                profile_id=_profile_id(work), work_unit_id=work.work_unit_id, output_language=OutputLanguage.EN
            ),
            ModeloWorkbenchFormProjectionV1,
        )
        assert reread.admitted_baseline is not None
        renewed = reread.admitted_baseline.to_baseline()
        fresh = ModeloEditOperatorInputV2(
            submission=ModeloEditApplySubmissionV1.from_submission(
                ModeloEditSubmissionV1(baseline=renewed, mutation_family=renewed.mutation_family, held=(mine, gone))
            ),
            output_language=OutputLanguage.EN,
        )
        moved, _ = _run(
            work, executor, MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID, fresh, ModeloEditPreflightProjectionV1
        )

    assert isinstance(unmoved.outcome, ModeloEditPreflightEvaluatedV1)
    assert [(entry.address, entry.outcome) for entry in unmoved.rebase] == [
        (mine.address, ModeloFormRebaseOutcome.KEPT),
        (gone.address, ModeloFormRebaseOutcome.DROPPED),
    ]
    # A preflight the stale baseline refuses judges nothing: the form it would judge against is about to change.
    assert isinstance(stale.outcome, ModeloEditRefusedV1)
    assert isinstance(stale.outcome.refusal, ModeloEditStaleBaselineRefusalV1)
    assert stale.rebase == ()
    assert isinstance(moved.outcome, ModeloEditPreflightEvaluatedV1)
    assert [(entry.address, entry.outcome) for entry in moved.rebase] == [
        (mine.address, ModeloFormRebaseOutcome.CHANGED),
        (gone.address, ModeloFormRebaseOutcome.DROPPED),
    ]
    # The digest stays in the transient submission: neither the journaled requests nor the result carry it.
    assert "held" not in ModeloEditPreflightRequestV2.model_fields
    assert "staged" not in ModeloEditRenewRequest.model_fields
    for result in (unmoved, stale, moved):
        assert box.state_digest not in result.model_dump_json()
    with pytest.raises(ValidationError):
        ModeloEditApplyRequestV1(operation_id="a" * 64, submission=submission)
